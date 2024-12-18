from flask_mail import Message
from flask import render_template, current_app
from . import mail

def send_order_confirmation(order):
    try:
        # Render the email template
        email_body = render_template(
            'email/order_confirmation.html',  # Fixed template path
            order=order,
            user=order.user
        )
        
        msg = Message('Order Confirmation - Stride',
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[order.email])
        msg.html = email_body
        
        # For now, just log the email
        current_app.logger.info(f"Order confirmation email would be sent to {order.email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending order confirmation email: {str(e)}")
        return False 