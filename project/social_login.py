from flask import Flask, render_template, redirect, url_for, flash, Blueprint, session, current_app, request
from flask_login import current_user, login_user
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized, oauth_error
from werkzeug.security import generate_password_hash
import secrets
from . import db
from .models import User
import traceback

# Initialize Google blueprint
blueprint = make_google_blueprint(
    client_id="your_client_id",
    client_secret="your_client_secret",
    scope=["profile", "email"],
    offline=True,
    redirect_url="/login/google/callback"
)

def init_oauth(app):
    print("Initializing OAuth...")
    try:
        app.register_blueprint(blueprint, url_prefix="/login")
        print("OAuth blueprint registered successfully")
    except Exception as e:
        print(f"Error initializing OAuth: {str(e)}")
        traceback.print_exc()

@blueprint.route("/google")
def google_login():
    print("Starting Google login process...")
    if not current_user.is_anonymous:
        print("User already logged in, redirecting to index")
        return redirect(url_for("main.index"))
    print("Redirecting to Google login")
    return redirect(url_for("google.login"))

@blueprint.route("/google/callback")
def google_callback():
    print("\n=== Starting Google Login Callback ===")
    
    if not google.authorized:
        print("Google not authorized")
        flash("Failed to log in with Google.", category="error")
        return redirect(url_for("auth.login"))

    try:
        print("Getting user info from Google...")
        resp = google.get("/oauth2/v2/userinfo")
        print(f"Google API Response Status: {resp.status_code}")
        
        if not resp.ok:
            print(f"Failed to get user info. Status: {resp.status_code}")
            print(f"Response content: {resp.text}")
            flash("Failed to get user info from Google.", category="error")
            return redirect(url_for("auth.login"))

        user_info = resp.json()
        print(f"Google user info received: {user_info}")
        
        if not user_info.get("email"):
            print("No email in user info")
            flash("Failed to get email from Google.", category="error")
            return redirect(url_for("auth.login"))

        print(f"Looking for user with email: {user_info['email']}")
        user = User.query.filter_by(email=user_info["email"]).first()
        
        if not user:
            print("Creating new user...")
            try:
                # Generate secure random password
                random_password = secrets.token_urlsafe(32)
                password_hash = generate_password_hash(random_password, method='sha256')
                
                # Create username from email or Google name
                base_username = user_info.get("name", "").replace(" ", "_").lower()
                if not base_username:
                    base_username = user_info["email"].split("@")[0]
                
                username = base_username
                counter = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                print(f"Generated username: {username}")
                
                # Create user
                user = User(
                    email=user_info["email"],
                    username=username,
                    password=password_hash,
                    profile_image=user_info.get("picture", "img/placeholder-profile.jpg")
                )
                
                print("Adding user to database...")
                db.session.add(user)
                db.session.commit()
                print(f"User created successfully: {user.email}")
                
            except Exception as db_error:
                print("=== Database Error ===")
                print(f"Error type: {type(db_error).__name__}")
                print(f"Error message: {str(db_error)}")
                traceback.print_exc()
                db.session.rollback()
                flash("Failed to create user account.", category="error")
                return redirect(url_for("auth.login"))
        else:
            print(f"Existing user found: {user.email}")

        # Check if user account is deactivated
        if not user.is_active:
            print("User account is deactivated")
            flash("Your account has been deactivated. Please contact an Support service.", category="error")
            return redirect(url_for("auth.login"))

        print("Logging in user...")
        login_user(user)
        print("User logged in successfully")
        
        flash("Successfully signed in with Google.", category="success")
        return redirect(url_for("main.index"))

    except Exception as e:
        print("\n=== Login Error ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()
        print("===================\n")
        
        flash("An error occurred during login. Please try again.", category="error")
        return redirect(url_for("auth.login"))

@oauth_error.connect_via(blueprint)
def google_error(blueprint, error, error_description=None, error_uri=None):
    print("\n=== OAuth Error ===")
    print(f"Error: {error}")
    print(f"Description: {error_description}")
    print(f"URI: {error_uri}")
    print("=================\n")
    
    flash("Failed to log in with Google. Please try again.", category="error")
    return redirect(url_for("auth.login"))



