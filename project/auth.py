from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import User, CartItem, Notification
from . import db, mail
from flask_mail import Message
import random
import time
import secrets
from .errors import (
    AuthError, InvalidCredentialsError, EmailNotFoundError,
    OTPError, PasswordResetError, EmailDeliveryError
)
from datetime import datetime, timedelta
import string
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Length, ValidationError
from urllib.parse import urlparse, urljoin
import os
from werkzeug.utils import secure_filename
from .forms import SellerRegistrationForm, SignupForm

auth = Blueprint('auth', __name__)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_otp_email(email, otp):
    try:
        # Log the start of email sending process
        current_app.logger.info(f"Starting OTP email send process to: {email}")
        
        # Create message with proper configuration
        msg = Message(
            'Password Reset Code - Stride',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email]
        )
        
        # Add template context with current time for valid_minutes
        msg.html = render_template(
            'email/reset_otp.html',
            otp=otp,
            valid_minutes=5,
            now=datetime.utcnow
        )
        
        # Log email configuration details
        current_app.logger.info(f"Email Configuration:")
        current_app.logger.info(f"- Server: {current_app.config.get('MAIL_SERVER')}")
        current_app.logger.info(f"- Port: {current_app.config.get('MAIL_PORT')}")
        current_app.logger.info(f"- Use TLS: {current_app.config.get('MAIL_USE_TLS')}")
        current_app.logger.info(f"- Sender: {msg.sender}")
        current_app.logger.info(f"- Recipients: {msg.recipients}")
        
        # Send the email with error catching
        try:
            mail.send(msg)
            current_app.logger.info(f"OTP email sent successfully to {email}")
            return True
        except Exception as mail_error:
            current_app.logger.error(f"Mail send error: {str(mail_error)}")
            if hasattr(mail_error, 'smtp_error'):
                current_app.logger.error(f"SMTP Error: {mail_error.smtp_error}")
            if hasattr(mail_error, 'smtp_code'):
                current_app.logger.error(f"SMTP Code: {mail_error.smtp_code}")
            raise
            
    except Exception as e:
        import traceback
        current_app.logger.error("Failed to send OTP email")
        current_app.logger.error(f"Error type: {type(e).__name__}")
        current_app.logger.error(f"Error message: {str(e)}")
        current_app.logger.error(f"Traceback:\n{traceback.format_exc()}")
        return False

def handle_auth_error(error):
    flash(error.message, error.category)
    return redirect(url_for('auth.login'))

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required")
    ])

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address")
    ])

class OTPForm(FlaskForm):
    otp1 = StringField('OTP1', validators=[DataRequired()])
    otp2 = StringField('OTP2', validators=[DataRequired()])
    otp3 = StringField('OTP3', validators=[DataRequired()])
    otp4 = StringField('OTP4', validators=[DataRequired()])
    otp5 = StringField('OTP5', validators=[DataRequired()])
    otp6 = StringField('OTP6', validators=[DataRequired()])

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=8, message="Password must be at least 8 characters long")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password"),
        Length(min=8, message="Password must be at least 8 characters long")
    ])

def url_is_safe(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        # Log login attempt
        current_app.logger.info(f"Login attempt for email: {email}")
        
        try:
            # Test database connection
            current_app.logger.info("Testing database connection...")
            db.session.execute('SELECT 1')
            current_app.logger.info("Database connection successful")
            
            # Query user with detailed logging
            current_app.logger.info(f"Querying user with email: {email}")
            user = User.query.filter_by(email=email).first()
            current_app.logger.info(f"Query complete. User found: {user is not None}")
            
            if not user:
                current_app.logger.warning(f"Login failed: No user found for email {email}")
                flash('No account found with that email address.', 'error')
                return render_template('auth/login.html', form=form)
            
            # Log password check attempt
            current_app.logger.info("Checking password hash...")
            current_app.logger.info(f"User has password hash: {user.password_hash is not None}")
            is_valid_password = check_password_hash(user.password_hash, password)
            current_app.logger.info(f"Password check result: {is_valid_password}")
            
            if not is_valid_password:
                current_app.logger.warning(f"Login failed: Invalid password for email {email}")
                flash('Invalid password.', 'error')
                return render_template('auth/login.html', form=form)
            
            # Check if account is deactivated
            if not user.is_active:
                current_app.logger.warning(f"Login failed: Account deactivated for email {email}")
                flash('Your account has been deactivated. Please contact support for assistance.', 'error')
                return render_template('auth/login.html', form=form)
            
            # Attempt to log in user
            current_app.logger.info(f"Attempting to login user: {user.email}")
            login_user(user, remember=True)
            current_app.logger.info("Login successful")
            
            flash('Login successful!', 'success')
            
            # Handle "next" parameter for redirecting after login
            next_page = request.args.get('next')
            if next_page and url_is_safe(next_page):
                return redirect(next_page)
            return redirect(url_for('main.index'))
            
        except Exception as e:
            import traceback
            current_app.logger.error("=== Login Error Details ===")
            current_app.logger.error(f"Error Type: {type(e).__name__}")
            current_app.logger.error(f"Error Message: {str(e)}")
            current_app.logger.error("Traceback:")
            current_app.logger.error(traceback.format_exc())
            current_app.logger.error("========================")
            
            # Attempt to rollback any failed transaction
            try:
                db.session.rollback()
                current_app.logger.info("Successfully rolled back database session")
            except Exception as rollback_error:
                current_app.logger.error(f"Rollback error: {str(rollback_error)}")
            
            flash('An error occurred during login. Please try again later.', 'error')
            return render_template('auth/login.html', form=form)
            
    # Display form validation errors
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                current_app.logger.warning(f"Form validation error - {field}: {error}")
                flash(f"{field}: {error}", 'error')
                
    return render_template('auth/login.html', form=form)

def get_cart_count():
    if current_user.is_authenticated:
        return CartItem.query.filter_by(user_id=current_user.id).count()
    return 0

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        try:
            email = form.email.data
            current_app.logger.info(f"Password reset requested for email: {email}")
            
            user = User.query.filter_by(email=email).first()
            if not user:
                current_app.logger.warning(f"No user found for email: {email}")
                raise EmailNotFoundError('No account found with that email address.')
            
            # Generate 6-digit OTP
            otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            current_app.logger.info(f"Generated OTP for {email}")
            
            session['reset_otp'] = otp
            session['reset_email'] = email
            session['otp_timestamp'] = time.time()
            
            if not send_otp_email(email, otp):
                raise EmailDeliveryError('Failed to send OTP email. Please try again.')
                
            flash('OTP has been sent to your email.', 'success')
            return redirect(url_for('auth.verify_otp'))
            
        except (EmailNotFoundError, EmailDeliveryError) as e:
            flash(e.message, 'error')
        except Exception as e:
            current_app.logger.error(f"Unexpected error in forgot_password: {str(e)}")
            flash('An unexpected error occurred. Please try again.', 'error')
    
    return render_template('auth/forgot_password.html', form=form)

@auth.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    form = OTPForm()
    if form.validate_on_submit():
        otp_digits = [
            form.otp1.data, form.otp2.data, form.otp3.data,
            form.otp4.data, form.otp5.data, form.otp6.data
        ]
        
        submitted_otp = ''.join(otp_digits)
        stored_otp = session.get('reset_otp')
        
        if submitted_otp == stored_otp:
            if time.time() - session.get('otp_timestamp', 0) <= 900:  # 15 minutes
                session['otp_verified'] = True
                flash('Verification successful! Please set your new password.', 'success')
                return redirect(url_for('auth.set_new_password'))
            else:
                flash('OTP has expired. Please request a new one.', 'error')
                return redirect(url_for('auth.forgot_password'))
        
        flash('Invalid verification code', 'error')
    return render_template('auth/verify_otp.html', form=form)

@auth.route('/set-new-password', methods=['GET', 'POST'])
def set_new_password():
    if 'reset_email' not in session or 'otp_verified' not in session:
        flash('Please complete the verification process first.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        email = session.get('reset_email')
        current_app.logger.info(f"Password reset attempt for email: {email}")
        
        try:
            # Validate passwords match
            if form.password.data != form.confirm_password.data:
                flash('Passwords do not match.', 'error')
                return render_template('auth/reset_password.html', form=form)
            
            # Find user
            user = User.query.filter_by(email=email).first()
            if not user:
                current_app.logger.error(f"User not found for email: {email}")
                flash('User not found.', 'error')
                return redirect(url_for('auth.forgot_password'))
            
            current_app.logger.info(f"Found user: {user.id}")
            
            # Update password using the model's setter method
            try:
                # This will automatically hash the password
                user.password = form.password.data
                db.session.commit()
                current_app.logger.info("Password updated successfully")
                
                # Clear session data
                for key in ['reset_email', 'otp_verified', 'reset_otp', 'otp_timestamp']:
                    session.pop(key, None)
                current_app.logger.info("Cleared session data")
                
                flash('Password has been reset successfully. Please login with your new password.', 'success')
                return redirect(url_for('auth.login'))
                
            except Exception as db_error:
                current_app.logger.error(f"Database error: {str(db_error)}")
                db.session.rollback()
                raise
            
        except Exception as e:
            current_app.logger.error("=== Password Reset Error ===")
            current_app.logger.error(f"Error type: {type(e).__name__}")
            current_app.logger.error(f"Error message: {str(e)}")
            current_app.logger.error("Traceback:", exc_info=True)
            current_app.logger.error("=========================")
            
            flash('An error occurred while resetting your password. Please try again.', 'error')
            return render_template('auth/reset_password.html', form=form)
    
    return render_template('auth/reset_password.html', form=form)

@auth.route('/resend-otp')
def resend_otp():
    email = session.get('reset_email')
    if not email:
        flash('Please start the password reset process again', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Please start the password reset process again', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    # Generate new OTP
    otp = ''.join(random.choices(string.digits, k=6))
    user.reset_token = otp
    user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()
    
    if not send_otp_email(email, otp):
        flash('Failed to send verification code. Please try again.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    flash('A new verification code has been sent to your email', 'info')
    return redirect(url_for('auth.verify_otp'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = SignupForm()
    try:
        if form.validate_on_submit():
            try:
                # Create new user with explicit values
                new_user = User()
                new_user.username = form.username.data
                new_user.email = form.email.data
                new_user.password_hash = generate_password_hash(form.password.data, method='sha256')
                new_user.phone = form.phone.data
                new_user.address = form.address.data
                new_user.profile_image = 'img/default-avatar.png'
                
                # Handle seller registration if is_seller is checked
                if form.is_seller.data:
                    new_user.is_seller = True
                    new_user.store_name = form.store_name.data
                    new_user.store_description = form.store_description.data
                    new_user.business_type = form.business_type.data
                    new_user.business_address = form.business_address.data
                    new_user.business_email = form.business_email.data
                    new_user.tax_id = form.tax_id.data
                    new_user.account_status = 'pending'
                    
                    # Handle profile image upload for seller
                    if form.profile_image.data:
                        file = form.profile_image.data
                        if file and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            filename = f"profile_{int(time.time())}_{filename}"
                            
                            # Create upload directory if it doesn't exist
                            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            # Save the file
                            filepath = os.path.join(upload_dir, filename)
                            file.save(filepath)
                            
                            # Update database path
                            new_user.profile_image = f'uploads/profiles/{filename}'
                
                # Log the registration
                current_app.logger.info("New user registration:")
                current_app.logger.info(f"Username: {new_user.username}")
                current_app.logger.info(f"Email: {new_user.email}")
                current_app.logger.info(f"Is Seller: {new_user.is_seller}")
                
                try:
                    db.session.add(new_user)
                    db.session.commit()
                    
                    # If user is a seller, send notifications and welcome email
                    if new_user.is_seller:
                        # Send notification to admin if admin exists
                        admin_user = User.query.filter_by(id=1).first()
                        if admin_user:
                            admin_notification = Notification(
                                user_id=admin_user.id,  # Use admin's actual ID
                                title='New Seller Registration',
                                message=f'New seller registration from {new_user.username}. Store name: {new_user.store_name}',
                                type='seller_registration'
                            )
                            db.session.add(admin_notification)
                            db.session.commit()
                        
                        # Send welcome email to seller
                        try:
                            msg = Message(
                                'Welcome to Stride Sellers!',
                                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                                recipients=[new_user.business_email]
                            )
                            msg.html = render_template(
                                'email/seller_welcome.html',
                                user=new_user,
                                store_name=new_user.store_name,
                                now=datetime.utcnow()
                            )
                            mail.send(msg)
                        except Exception as e:
                            current_app.logger.error(f"Failed to send welcome email: {str(e)}")
                    
                    # Log in the new user
                    login_user(new_user)
                    
                    # Show appropriate success message
                    if new_user.is_seller:
                        flash('Registration successful! Your seller account is pending approval.', 'success')
                    else:
                        flash('Registration successful!', 'success')
                        
                    return redirect(url_for('main.index'))
                    
                except Exception as db_error:
                    current_app.logger.error(f"Database error: {str(db_error)}")
                    db.session.rollback()
                    raise
                
            except Exception as e:
                current_app.logger.error("Registration error details:")
                current_app.logger.error(f"Error type: {type(e).__name__}")
                current_app.logger.error(f"Error message: {str(e)}")
                current_app.logger.error("Error traceback:", exc_info=True)
                db.session.rollback()
                flash(f'Registration error: {str(e)}', 'error')
                
    except Exception as outer_error:
        current_app.logger.error(f"Outer error: {str(outer_error)}")
        flash(f'Form validation error: {str(outer_error)}', 'error')
        
    # Display form validation errors
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'error')
                current_app.logger.error(f"Form error - {field}: {error}")
    
    return render_template('auth/signup.html', form=form)

@auth.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_authenticated:
        flash('You do not have permission to access the admin panel.', 'error')
        return redirect(url_for('main.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        try:
            user = User.query.filter_by(email=email).first()
            
            if not user or not user.is_admin:
                flash('Invalid admin credentials.', 'error')
                return render_template('auth/admin_login.html', form=form)
            
            if not check_password_hash(user.password_hash, password):
                flash('Invalid password.', 'error')
                return render_template('auth/admin_login.html', form=form)
            
            # Check if account is deactivated
            if not user.is_active:
                flash('Your account has been deactivated. Please contact the system administrator.', 'error')
                return render_template('auth/admin_login.html', form=form)
            
            login_user(user, remember=True)
            flash('Welcome to the admin panel!', 'success')
            return redirect(url_for('admin.dashboard'))
            
        except Exception as e:
            current_app.logger.error(f"Admin login error: {str(e)}")
            flash('An error occurred during login. Please try again.', 'error')
            
    return render_template('auth/admin_login.html', form=form)

@auth.route('/become-seller', methods=['GET', 'POST'])
@login_required
def become_seller():
    if current_user.is_seller:
        flash('You are already registered as a seller', 'info')
        return redirect(url_for('product.seller_dashboard'))
        
    form = SellerRegistrationForm()
    
    if form.validate_on_submit():
        try:
            # Update user as seller
            current_user.is_seller = True
            current_user.store_name = form.store_name.data
            current_user.store_description = form.store_description.data
            current_user.business_type = form.business_type.data
            current_user.business_address = form.business_address.data
            current_user.phone = form.phone.data
            current_user.business_email = form.business_email.data
            current_user.tax_id = form.tax_id.data
            current_user.account_status = 'pending'
            
            # Handle profile image upload
            if form.profile_image.data:
                file = form.profile_image.data
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filename = f"profile_{current_user.id}_{int(time.time())}_{filename}"
                    
                    # Create upload directory if it doesn't exist
                    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Save the file
                    filepath = os.path.join(upload_dir, filename)
                    file.save(filepath)
                    
                    # Update database path
                    current_user.profile_image = f'uploads/profiles/{filename}'
            
            # Log the seller registration
            current_app.logger.info(f"New seller registration - User ID: {current_user.id}")
            current_app.logger.info(f"Store Name: {current_user.store_name}")
            current_app.logger.info(f"Business Type: {current_user.business_type}")
            
            # Send notification to admin
            admin_notification = Notification(
                user_id=1,  # Assuming admin has ID 1
                title='New Seller Registration',
                message=f'New seller registration from {current_user.username}. Store name: {current_user.store_name}',
                type='seller_registration'
            )
            db.session.add(admin_notification)
            
            # Send welcome email to seller
            try:
                msg = Message(
                    'Welcome to Stride Sellers!',
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[current_user.business_email]
                )
                msg.html = render_template(
                    'email/seller_welcome.html',
                    user=current_user,
                    store_name=current_user.store_name
                )
                mail.send(msg)
            except Exception as e:
                current_app.logger.error(f"Failed to send welcome email: {str(e)}")
            
            db.session.commit()
            
            flash('Successfully registered as a seller! Your account is pending approval.', 'success')
            return redirect(url_for('product.seller_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in seller registration: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'error')
    
    return render_template('auth/seller_registration.html', form=form)

