from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.pool import QueuePool
from sqlalchemy import event
import os
import logging
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager
import time
from typing import Optional, Any
from sqlalchemy.orm import Session as SQLAlchemySession

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
mail = Mail()
csrf = CSRFProtect()
login_manager = LoginManager()

@contextmanager
def session_scope() -> Any:
    """Provide a transactional scope around a series of operations."""
    session: SQLAlchemySession = db.create_scoped_session()
    max_retries = 3
    retry_count = 0
    
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def create_app():
    app = Flask(__name__)

    # Basic configuration
    app.config['SECRET_KEY'] = 'your_secret_key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:@localhost:3306/Your database_name '
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Configure upload paths
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    app.config['PROFILE_UPLOAD_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles')
    
    # Create upload directories if they don't exist
    for directory in [app.config['UPLOAD_FOLDER'], app.config['PROFILE_UPLOAD_FOLDER']]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")
    
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Profile upload folder: {app.config['PROFILE_UPLOAD_FOLDER']}")
    
    # MySQL specific configuration
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 30,
        'max_overflow': 40,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 120,
        'pool_use_lifo': True,
        'echo': True if not app.debug else False,
        'echo_pool': True,
        'pool_reset_on_return': 'rollback',
        'execution_options': {
            'timeout': 60,
            'autocommit': False
        }
    }
    
    # Email configuration
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'YourEmail')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'Your password')
    app.config['MAIL_DEFAULT_SENDER'] = ('Stride Support', os.environ.get('MAIL_USERNAME', 'YourEmail'))
    app.config['MAIL_MAX_EMAILS'] = 50
    app.config['MAIL_ASCII_ATTACHMENTS'] = False
    app.config['MAIL_DEBUG'] = True
    app.config['MAIL_SUPPRESS_SEND'] = False
    app.config['MAIL_FAIL_SILENTLY'] = True
    app.config['MAIL_TIMEOUT'] = 30
    app.config['MAIL_KEEP_ALIVE'] = True
    
    # Configure mail logging
    if not app.debug:
        mail_handler = logging.handlers.SMTPHandler(
            mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
            fromaddr=app.config['MAIL_DEFAULT_SENDER'][1],
            toaddrs=['admin@stride.com'],
            subject='Stride Application Error',
            credentials=(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD']),
            secure=() if app.config['MAIL_USE_TLS'] else None
        )
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)
    
    # OAuth configuration
    app.config['GOOGLE_OAUTH_CLIENT_ID'] = "your client_ID"
    app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = "your Client secret"
    app.config['OAUTHLIB_INSECURE_TRANSPORT'] = True
    app.config['OAUTHLIB_RELAX_TOKEN_SCOPE'] = True
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['GOOGLE_OAUTH_REDIRECT_URI'] = 'http://127.0.0.1:5000/login/google/authorized'
    app.config['SECRET_KEY'] = 'ES3naid0V2'
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

    # Configure logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.makedirs('logs')
        file_handler = RotatingFileHandler('logs/stride.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Stride startup')

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from .models import User, OAuth, CartItem, Category

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional['User']:
        try:
            with session_scope() as session:
                user = session.query(User).get(int(user_id))
                if user:
                    session.expunge(user)
                return user
        except Exception as e:
            current_app.logger.error(f"Error loading user {user_id}: {str(e)}")
            return None

    # Global context processor for categories
    @app.context_processor
    def inject_categories():
        try:
            with session_scope() as session:
                categories = session.query(Category).order_by(Category.name).all()
                for category in categories:
                    session.expunge(category)
                return dict(categories=categories)
        except Exception as e:
            app.logger.error(f"Error in categories context processor: {str(e)}")
            return dict(categories=[])

    # Global context processor for cart count
    @app.context_processor
    def inject_cart_data():
        if current_user.is_authenticated:
            try:
                with session_scope() as session:
                    cart_items = session.query(CartItem).filter_by(user_id=current_user.id).all()
                    for item in cart_items:
                        session.expunge(item)
                    return dict(cart_items=cart_items, cart_count=len(cart_items))
            except Exception as e:
                app.logger.error(f"Error in cart context processor: {str(e)}")
                return dict(cart_items=[], cart_count=0)
        return dict(cart_items=[], cart_count=0)

    # Register blueprints
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix="/admin")

    from .auth import auth
    from .product import product
    from .social_login import blueprint as google_blueprint, init_oauth

    app.register_blueprint(auth)
    app.register_blueprint(product, url_prefix="/product")
    
    # Initialize OAuth with proper URL prefix
    init_oauth(app)

    # Session cleanup
    @app.teardown_appcontext
    def cleanup(exc):
        try:
            db.session.remove()
        except Exception as e:
            app.logger.error(f"Error in cleanup: {str(e)}")

    # Set up database connection event handlers
    with app.app_context():
        @event.listens_for(db.engine, 'connect')
        def connect(dbapi_connection, connection_record):
            """Configure MySQL session variables for better performance."""
            try:
                cursor = dbapi_connection.cursor()
                # Increase timeouts
                cursor.execute("SET SESSION wait_timeout = 86400")  # 24 hours
                cursor.execute("SET SESSION interactive_timeout = 86400")  # 24 hours
                # Optimize for performance
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 120")  # 2 minutes
                cursor.execute("SET SESSION net_write_timeout = 120")  # 2 minutes
                cursor.execute("SET SESSION net_read_timeout = 120")  # 2 minutes
                cursor.close()
            except Exception as e:
                current_app.logger.error(f"Error setting session variables: {str(e)}")

        @event.listens_for(db.engine, 'checkout')
        def checkout(dbapi_connection, connection_record, connection_proxy):
            app.logger.info('Database connection checked out')
            try:
                # Verify connection is still valid
                cursor = dbapi_connection.cursor()
                cursor.execute('SELECT 1')
                cursor.close()
            except Exception as e:
                app.logger.error(f"Connection invalid at checkout: {str(e)}")
                connection_proxy._pool.dispose()
                raise

        @event.listens_for(db.engine, 'checkin')
        def checkin(dbapi_connection, connection_record):
            app.logger.info('Database connection checked in')
            try:
                # Reset session state
                cursor = dbapi_connection.cursor()
                cursor.execute("SET SESSION wait_timeout = DEFAULT")
                cursor.execute("SET SESSION interactive_timeout = DEFAULT")
                cursor.close()
            except Exception as e:
                app.logger.error(f"Error resetting session state: {str(e)}")

        @event.listens_for(db.engine, 'reset')
        def reset(dbapi_connection, connection_record):
            app.logger.info('Database connection reset')
            try:
                # Verify connection is still valid after reset
                cursor = dbapi_connection.cursor()
                cursor.execute('SELECT 1')
                cursor.close()
            except Exception as e:
                app.logger.error(f"Connection invalid after reset: {str(e)}")
                raise

    return app
