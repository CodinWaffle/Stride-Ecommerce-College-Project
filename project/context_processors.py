from flask_login import current_user
from .models import CartItem, Category

def utility_processor():
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    
    def get_categories():
        return Category.query.all()
    
    return dict(
        cart_count=cart_count,
        categories=get_categories()
    ) 