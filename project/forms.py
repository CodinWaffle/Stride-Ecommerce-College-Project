from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length, Email, ValidationError, Regexp, Optional
from flask_wtf.file import FileField, FileAllowed
import re
from flask import current_app

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=80, message="Username must be between 3 and 80 characters")
    ])
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address")
    ])
    phone = StringField('Phone Number', validators=[
        DataRequired(message="Phone number is required"),
        Length(min=10, max=15, message="Please enter a valid phone number"),
        Regexp(r'^\+?1?\d{9,15}$', message="Please enter a valid phone number")
    ])
    address = StringField('Address', validators=[
        DataRequired(message="Address is required"),
        Length(min=5, max=200, message="Address must be between 5 and 200 characters")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=8, message="Password must be at least 8 characters long")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password"),
        Length(min=8, message="Password must be at least 8 characters long")
    ])
    is_seller = BooleanField('Register as Seller')

    # Profile Image
    profile_image = FileField('Profile Image', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])

    # Seller specific fields
    store_name = StringField('Store Name', validators=[
        Optional(),
        Length(min=3, max=100, message="Store name must be between 3 and 100 characters"),
        Regexp(r'^[\w\s-]*$', message="Store name can only contain letters, numbers, spaces, and dashes")
    ])
    store_description = TextAreaField('Store Description', validators=[
        Optional(),
        Length(min=20, max=500, message="Description must be between 20 and 500 characters")
    ])
    business_type = SelectField('Business Type', 
        choices=[
            ('', 'Select Business Type'),
            ('individual', 'Individual Seller'),
            ('registered_business', 'Registered Business'),
            ('partnership', 'Partnership'),
            ('other', 'Other')
        ],
        validators=[Optional()]
    )
    business_address = StringField('Business Address', validators=[
        Optional(),
        Length(min=10, max=200, message="Address must be between 10 and 200 characters")
    ])
    business_email = StringField('Business Email', validators=[
        Optional(),
        Email(message="Please enter a valid email address"),
        Length(max=120)
    ])
    tax_id = StringField('Tax ID (Optional)', validators=[
        Optional(),
        Length(max=50, message="Tax ID must not exceed 50 characters"),
        Regexp(r'^[A-Z0-9-]*$', message="Tax ID can only contain uppercase letters, numbers, and dashes")
    ])

    def validate_confirm_password(self, field):
        if field.data != self.password.data:
            raise ValidationError('Passwords must match')

    def validate_username(self, field):
        from .models import User  # Import here to avoid circular imports
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

    def validate_email(self, field):
        from .models import User  # Import here to avoid circular imports
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email address already exists')

    def validate_store_name(self, field):
        if self.is_seller.data and field.data:
            from .models import User  # Import here to avoid circular imports
            if User.query.filter_by(store_name=field.data).first():
                raise ValidationError('This store name is already taken')

    def validate_business_email(self, field):
        if self.is_seller.data and field.data:
            from .models import User  # Import here to avoid circular imports
            if User.query.filter_by(business_email=field.data).first():
                raise ValidationError('This business email is already registered')

    def validate_on_submit(self):
        if not super(SignupForm, self).validate_on_submit():
            return False

        if self.is_seller.data:
            # Additional validation for seller fields when is_seller is checked
            if not self.store_name.data:
                self.store_name.errors = ['Store name is required for sellers']
                return False
            if not self.store_description.data:
                self.store_description.errors = ['Store description is required for sellers']
                return False
            if not self.business_type.data:
                self.business_type.errors = ['Business type is required for sellers']
                return False
            if not self.business_address.data:
                self.business_address.errors = ['Business address is required for sellers']
                return False
            if not self.business_email.data:
                self.business_email.errors = ['Business email is required for sellers']
                return False

        return True

class SellerRegistrationForm(FlaskForm):
    store_name = StringField('Store Name', validators=[
        DataRequired(message="Store name is required"),
        Length(min=3, max=100, message="Store name must be between 3 and 100 characters"),
        Regexp(r'^[\w\s-]+$', message="Store name can only contain letters, numbers, spaces, and dashes")
    ])
    store_description = TextAreaField('Store Description', validators=[
        DataRequired(message="Store description is required"),
        Length(min=20, max=500, message="Description must be between 20 and 500 characters")
    ])
    business_type = SelectField('Business Type', 
        choices=[
            ('', 'Select Business Type'),
            ('individual', 'Individual Seller'),
            ('registered_business', 'Registered Business'),
            ('partnership', 'Partnership'),
            ('other', 'Other')
        ],
        validators=[DataRequired(message="Please select your business type")]
    )
    business_address = StringField('Business Address', validators=[
        DataRequired(message="Business address is required"),
        Length(min=10, max=200, message="Address must be between 10 and 200 characters")
    ])
    business_email = StringField('Business Email', validators=[
        DataRequired(message="Business email is required"),
        Email(message="Please enter a valid email address"),
        Length(max=120)
    ])
    tax_id = StringField('Tax ID (Optional)', validators=[
        Optional(),
        Length(max=50, message="Tax ID must not exceed 50 characters"),
        Regexp(r'^[A-Z0-9-]*$', message="Tax ID can only contain uppercase letters, numbers, and dashes")
    ])
    profile_image = FileField('Profile Image', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])
    submit = SubmitField('Register as Seller')

    def validate_store_name(self, field):
        from .models import User  # Import here to avoid circular imports
        if User.query.filter_by(store_name=field.data).first():
            raise ValidationError('This store name is already taken')

    def validate_business_email(self, field):
        from .models import User  # Import here to avoid circular imports
        if User.query.filter_by(business_email=field.data).first():
            raise ValidationError('This business email is already registered') 