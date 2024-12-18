class AuthError(Exception):
    """Base authentication error"""
    def __init__(self, message, category='error'):
        self.message = message
        self.category = category
        super().__init__(self.message)

class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid"""
    pass

class EmailNotFoundError(AuthError):
    """Raised when email doesn't exist"""
    pass

class OTPError(AuthError):
    """Raised when there's an OTP-related error"""
    pass

class PasswordResetError(AuthError):
    """Raised when there's an error during password reset"""
    pass

class EmailDeliveryError(AuthError):
    """Raised when email sending fails"""
    pass 