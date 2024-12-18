from flask import current_app, render_template
from flask_mail import Message
from . import mail
import logging
import traceback

def send_otp_email(email, otp):
    """Send OTP email for password reset."""
    try:
        print("Starting email send process...")
        print(f"Email: {email}")
        print(f"OTP: {otp}")
        
        # Create message with direct values
        msg = Message()
        msg.subject = 'Password Reset Code - Stride'
        msg.sender = 'dnxncpcx@gmail.com'  # Direct sender
        msg.recipients = [email]
        
        # Simple HTML message
        msg.html = f"""
        <h2>Password Reset Code</h2>
        <p>Your verification code is: <strong>{otp}</strong></p>
        <p>This code will expire in 30 minutes.</p>
        """
        
        print("Message created, attempting to send...")
        print(f"Subject: {msg.subject}")
        print(f"Sender: {msg.sender}")
        print(f"Recipients: {msg.recipients}")
        
        # Send email
        mail.send(msg)
        print("Email sent successfully!")
        return True
        
    except Exception as e:
        print("=== Email Sending Error ===")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print("Full traceback:")
        traceback.print_exc()
        print("========================")
        return False 