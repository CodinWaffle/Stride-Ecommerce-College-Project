from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify, current_app, abort, session, Flask
from flask_login import login_required, current_user
from .models import Product, Category, CartItem, Order, OrderItem, User, Review, ShipmentTracking, ReviewImage, Message
from . import db, session_scope
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, scoped_session
from sqlalchemy.orm.session import make_transient
from typing import Dict, Any, Optional, Union
from .utils import send_order_confirmation
import os
from werkzeug.utils import secure_filename
import time
from datetime import datetime
from sqlalchemy.sql import func
import uuid
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, EmailField
from wtforms.validators import DataRequired, Email, Length
from flask_mail import Mail, Message

# Initialize Flask-Mail
mail = Mail()

main = Blueprint('main', __name__)

# Get the absolute path to the project directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(PROJECT_DIR, 'static')
UPLOAD_FOLDER = os.path.join(STATIC_DIR, 'uploads')
PROFILE_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'profiles')

# Create all required directories
for directory in [STATIC_DIR, UPLOAD_FOLDER, PROFILE_UPLOAD_FOLDER]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

print(f"Project directory: {PROJECT_DIR}")
print(f"Static directory: {STATIC_DIR}")
print(f"Upload folder: {UPLOAD_FOLDER}")
print(f"Profile upload folder: {PROFILE_UPLOAD_FOLDER}")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class CheckoutForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=80)])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=6, max=20)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    address = TextAreaField('Shipping Address', validators=[DataRequired(), Length(min=10, max=500)])

@main.route('/')
def index() -> str:
    try:
        # Get trending products (most sold or recently added)
        featured_products = Product.query\
            .order_by(Product.sold_count.desc())\
            .limit(6)\
            .all()
        
        return render_template('index.html', 
                            featured_products=featured_products)
    except Exception as e:
        current_app.logger.error(f"Error in index route: {str(e)}")
        return render_template('index.html', 
                            featured_products=[],
                            error="Unable to load featured products")

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile() -> str:
    try:
        # Get user with a fresh query and lock the row for update
        user = db.session.query(User).with_for_update().get(current_user.id)
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('main.index'))

        if request.method == 'POST':
            try:
                print("Received form data:", request.form.to_dict())
                print("Received files:", request.files)
                
                # Create a dictionary of updates
                updates = {}
                
                # Handle profile image upload if provided
                if 'profile_image' in request.files:
                    file = request.files['profile_image']
                    print(f"Profile image file: {file.filename if file else 'No file'}")
                    
                    if file and file.filename:
                        if allowed_file(file.filename):
                            try:
                                # Create profile upload directory if it doesn't exist
                                if not os.path.exists(PROFILE_UPLOAD_FOLDER):
                                    os.makedirs(PROFILE_UPLOAD_FOLDER)
                                
                                # Generate unique filename
                                filename = f"{user.id}_{int(time.time())}_{secure_filename(file.filename)}"
                                file_path = os.path.join(PROFILE_UPLOAD_FOLDER, filename)
                                
                                # Save the file
                                file.save(file_path)
                                print(f"Saved profile image to: {file_path}")
                                
                                # Store only the relative path from the static directory
                                relative_path = f"uploads/profiles/{filename}"
                                updates['profile_image'] = relative_path
                                print(f"Profile image path to be saved: {relative_path}")
                            except Exception as img_error:
                                print(f"Error saving profile image: {str(img_error)}")
                                flash('Error uploading profile image. Please try again.', 'error')
                        else:
                            flash('Invalid file type. Please upload an image file.', 'error')

                # Add form fields to updates if they exist and have changed
                form_fields = ['username', 'email', 'phone', 'address']
                for field in form_fields:
                    if field in request.form and request.form[field] != getattr(user, field):
                        updates[field] = request.form[field]

                # Handle seller-specific fields
                if user.is_seller:
                    seller_fields = ['store_name', 'store_description']
                    for field in seller_fields:
                        if field in request.form and request.form[field] != getattr(user, field):
                            updates[field] = request.form[field]

                print("Updates to be applied:", updates)

                if updates:
                    # Update the user object with the changes
                    for key, value in updates.items():
                        setattr(user, key, value)
                    
                    try:
                        # Commit the transaction
                        db.session.commit()
                        print("Changes committed successfully")
                        
                        # Verify the changes
                        db.session.refresh(user)
                        print("User data after update:", {
                            'username': user.username,
                            'email': user.email,
                            'phone': user.phone,
                            'address': user.address,
                            'profile_image': user.profile_image,
                            'store_name': user.store_name if user.is_seller else None,
                            'store_description': user.store_description if user.is_seller else None
                        })
                        
                        flash('Profile updated successfully!', 'success')
                    except Exception as commit_error:
                        db.session.rollback()
                        print(f"Error committing changes: {str(commit_error)}")
                        flash('Error saving changes. Please try again.', 'error')
                else:
                    print("No changes detected")
                    flash('No changes were made to your profile.', 'info')

                return redirect(url_for('main.profile'))
                
            except Exception as e:
                db.session.rollback()
                print(f"Error in profile update: {str(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                flash('Error updating profile. Please try again.', 'error')
                return redirect(url_for('main.profile'))
    
    except Exception as e:
        print(f"Error loading profile: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash('Error loading profile', 'error')
        return redirect(url_for('main.index'))
    
    return render_template('profile.html', user=user)

@main.route('/shop')
def shop() -> str:
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    # Get filter parameters
    category_id = request.args.get('category', type=int)
    sort = request.args.get('sort', 'newest')
    min_price = request.args.get('min_price', type=float, default=0)
    max_price = request.args.get('max_price', type=float)
    search_query = request.args.get('search', '').strip()
    
    # Base query
    query = Product.query.filter_by(is_active=True, is_archived=False)
    
    # Apply search filter if specified
    if search_query:
        search_terms = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search_terms),
                Product.description.ilike(search_terms),
                Product.category.has(Category.name.ilike(search_terms))
            )
        )
    
    # Apply category filter if specified
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    # Apply price range filter
    query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    
    # Apply sorting
    if sort == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_high':
        query = query.order_by(Product.price.desc())
    elif sort == 'popular':
        query = query.order_by(Product.sold_count.desc())
    else:  # newest
        query = query.order_by(Product.created_at.desc())
    
    # Get paginated products
    products = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all categories for the filter
    categories = Category.query.all()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return only the products grid for AJAX requests
        return render_template('includes/product_grid.html', products=products)
    
    return render_template('shop.html',
                         products=products,
                         categories=categories,
                         current_category=category_id,
                         current_sort=sort,
                         min_price=min_price,
                         max_price=max_price,
                         search_query=search_query)

@main.route('/about')
def about() -> str:
    return render_template('about.html')

@main.route('/contact')
def contact() -> str:
    return render_template('contact.html')

@main.route('/privacy-policy')
def privacy_policy() -> str:
    return render_template('privacy-policy.html', current_date=datetime.now().strftime('%B %d, %Y'))

@main.route('/terms-of-service')
def terms_of_service() -> str:
    return render_template('terms-of-service.html', current_date=datetime.now().strftime('%B %d, %Y'))

@main.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id: int) -> Dict[str, Any]:
    try:
        # Log the incoming request data
        print(f"Received add to cart request - Product ID: {product_id}")
        print(f"Request JSON: {request.json}")
        print(f"Request Headers: {request.headers}")
        
        # Get product with row lock
        product = db.session.query(Product).filter_by(id=product_id).with_for_update().first_or_404()
        quantity = request.json.get('quantity', 1)
        size = request.json.get('size')
        
        print(f"Processing - Product: {product.name}, Quantity: {quantity}, Size: {size}")
        
        if not size:
            print("Error: No size selected")
            return jsonify({
                'success': False,
                'message': 'Please select a size'
            }), 400
        
        if quantity > product.stock:
            print(f"Error: Not enough stock. Requested: {quantity}, Available: {product.stock}")
            return jsonify({
                'success': False,
                'message': 'Not enough stock available'
            }), 400
            
        if quantity < 1:
            print(f"Error: Invalid quantity: {quantity}")
            return jsonify({
                'success': False,
                'message': 'Quantity must be at least 1'
            }), 400
            
        # Check if item already in cart with same size using row lock
        cart_item = db.session.query(CartItem).filter_by(
            user_id=current_user.id,
            product_id=product_id,
            size=size
        ).with_for_update().first()
        
        try:
            with db.session.begin_nested():
                if cart_item:
                    print(f"Updating existing cart item - Current quantity: {cart_item.quantity}")
                    # Update quantity if already in cart
                    cart_item.quantity += quantity
                    if cart_item.quantity > product.stock:
                        print(f"Error: Total quantity exceeds stock. New total would be: {cart_item.quantity}")
                        return jsonify({
                            'success': False,
                            'message': 'Not enough stock available'
                        }), 400
                else:
                    print("Creating new cart item")
                    # Add new item to cart
                    cart_item = CartItem(
                        user_id=current_user.id,
                        product_id=product_id,
                        quantity=quantity,
                        size=size
                    )
                    db.session.add(cart_item)
                
                db.session.flush()  # Flush changes to detect any database errors
            
            # If we get here, the nested transaction succeeded
            db.session.commit()
            print("Successfully added/updated cart item")
            
            # Get updated cart count with a fresh query
            cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
            
            return jsonify({
                'success': True,
                'message': 'Added to cart successfully',
                'cart_count': cart_count
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"Database error: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'Error updating cart'
            }), 500
            
    except Exception as e:
        db.session.rollback()
        print(f"Error adding to cart: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@main.route('/cart')
@login_required
def cart() -> str:
    try:
        # Get cart items with eager loading of product relationship
        cart_items = CartItem.query\
            .filter_by(user_id=current_user.id)\
            .join(CartItem.product)\
            .all()
        
        # Calculate totals
        subtotal = sum(item.product.price * item.quantity for item in cart_items)
        shipping = 10 if subtotal > 0 else 0
        total = subtotal + shipping
        
        return render_template('cart.html',
                            cart_items=cart_items,
                            subtotal=subtotal,
                            shipping=shipping,
                            total=total)
    except Exception as e:
        current_app.logger.error(f"Error in cart route: {str(e)}")
        return render_template('cart.html',
                            cart_items=[],
                            subtotal=0,
                            shipping=0,
                            total=0,
                            error="Unable to load cart")

@main.context_processor
def inject_cart_data() -> Dict[str, Any]:
    if current_user.is_authenticated:
        try:
            cart_items = CartItem.query\
                .filter_by(user_id=current_user.id)\
                .join(CartItem.product)\
                .all()
            return dict(cart_items=cart_items, cart_count=len(cart_items))
        except Exception as e:
            current_app.logger.error(f"Error in cart context processor: {str(e)}")
            return dict(cart_items=[], cart_count=0)
    return dict(cart_items=[], cart_count=0)

@main.route('/orders')
@login_required
def orders() -> str:
    status_filter = request.args.get('status', 'all')
    
    query = Order.query.filter_by(user_id=current_user.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
        
    orders = query.order_by(Order.created_at.desc()).all()
    
    order_status_colors = {
        'pending': 'warning',
        'processing': 'info',
        'shipped': 'primary',
        'delivered': 'success',
        'cancelled': 'danger'
    }
    
    return render_template('orders.html', 
                         orders=orders,
                         order_status_colors=order_status_colors)

@main.route('/cart/update/<int:product_id>', methods=['POST'])
@login_required
def update_cart(product_id: int) -> Dict[str, Any]:
    try:
        print(f"Updating cart for product {product_id}")
        print(f"Request headers: {request.headers}")
        print(f"Request data: {request.get_data()}")
        
        # Try to get quantity from different possible sources
        quantity = None
        if request.form:
            quantity = request.form.get('quantity')
            print(f"Form quantity: {quantity}")
        elif request.json:
            quantity = request.json.get('quantity')
            print(f"JSON quantity: {quantity}")
            
        print(f"Final quantity value: {quantity}")
        
        if not quantity:
            print("No quantity provided")
            return jsonify({
                'success': False,
                'error': 'No quantity provided'
            }), 400
            
        try:
            quantity = int(quantity)
            print(f"Parsed quantity: {quantity}")
        except (TypeError, ValueError) as e:
            print(f"Error parsing quantity: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Invalid quantity format'
            }), 400
            
        # Get cart item with product details and lock the row
        cart_item = db.session.query(CartItem).filter_by(
            user_id=current_user.id,
            product_id=product_id
        ).with_for_update().first()

        if not cart_item:
            print(f"Cart item not found for user {current_user.id} and product {product_id}")
            return jsonify({
                'success': False,
                'error': 'Cart item not found'
            }), 404
            
        print(f"Found cart item: {cart_item.id}")
        
        # Lock the product row to check stock
        product = db.session.query(Product).filter_by(id=product_id).with_for_update().first()
        if not product:
            return jsonify({
                'success': False,
                'error': 'Product not found'
            }), 404
            
        print(f"Current stock: {product.stock}")
        
        if quantity > product.stock:
            print(f"Not enough stock. Requested: {quantity}, Available: {product.stock}")
            return jsonify({
                'success': False,
                'error': 'Not enough stock available'
            }), 400
            
        if quantity < 1:
            print(f"Invalid quantity: {quantity}")
            return jsonify({
                'success': False,
                'error': 'Quantity must be at least 1'
            }), 400
            
        # Update the quantity within a nested transaction
        with db.session.begin_nested():
            cart_item.quantity = quantity
            db.session.flush()  # Flush changes to detect any database errors
        
        # If we get here, the nested transaction succeeded
        db.session.commit()
        print("Successfully updated cart item quantity")
        
        # Calculate updated totals with a fresh query
        cart_items = CartItem.query.filter_by(user_id=current_user.id)\
            .join(CartItem.product)\
            .all()
            
        subtotal = float(sum(item.product.price * item.quantity for item in cart_items))
        shipping = 10.0 if subtotal > 0 else 0.0
        total = float(subtotal + shipping)
        
        # Calculate this item's new total
        item_total = float(product.price * quantity)
        
        print(f"Updated totals - Subtotal: {subtotal}, Shipping: {shipping}, Total: {total}")
        
        return jsonify({
            'success': True,
            'message': 'Cart updated successfully',
            'cart_count': len(cart_items),
            'subtotal': round(subtotal, 2),
            'shipping': round(shipping, 2),
            'total': round(total, 2),
            'newPrice': round(item_total, 2)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating cart: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Error updating cart',
            'message': str(e)
        }), 500

@main.route('/cart/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_from_cart(product_id: int) -> Dict[str, Any]:
    try:
        # First, get the cart item ID
        cart_item = CartItem.query.filter_by(
            user_id=current_user.id,
            product_id=product_id
        ).first_or_404()
        
        # Store the ID
        cart_item_id = cart_item.id
        
        # Delete the cart item
        db.session.query(CartItem).filter_by(id=cart_item_id).delete()
        db.session.commit()
        
        # After committing the delete, calculate totals with a fresh query
        remaining_cart_items = CartItem.query.filter_by(user_id=current_user.id)\
            .join(CartItem.product)\
            .all()
        
        # Calculate totals from the new query
        subtotal = float(sum(item.product.price * item.quantity for item in remaining_cart_items))
        shipping = 10.0 if subtotal > 0 else 0.0
        total = float(subtotal + shipping)
        cart_count = len(remaining_cart_items)
        
        # Ensure all numbers are properly formatted
        return jsonify({
            'success': True,
            'message': 'Item removed from cart',
            'subtotal': round(subtotal, 2),
            'shipping': round(shipping, 2),
            'total': round(total, 2),
            'cart_count': cart_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error removing item from cart: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Error removing item from cart',
            'message': str(e)
        }), 500

def send_order_confirmation(order: Order) -> bool:
    try:
        # Render the email template
        email_body = render_template(
            'email/order_confirmation.html',
            order=order,
            user=order.user
        )
        
        # For now, just log the email
        current_app.logger.info(f"Order confirmation email would be sent to {order.email}")
        current_app.logger.info(f"Email content: {email_body}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending order confirmation email: {str(e)}")
        return False

@main.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout() -> str:
    try:
        current_app.logger.info("Starting checkout process")
        form = CheckoutForm()
        
        # Check if this is a direct checkout
        direct_checkout_data = session.get('direct_checkout')
        current_app.logger.info(f"Direct checkout data: {direct_checkout_data}")
        
        with session_scope() as db_session:
            if direct_checkout_data:
                # Get product for direct checkout with eager loading
                product = db_session.query(Product).options(
                    db.joinedload(Product.seller)
                ).get(direct_checkout_data['product_id'])
                
                if not product:
                    flash('Product not found', 'error')
                    return redirect(url_for('main.shop'))
                
                # Create a temporary cart item
                class TempCartItem:
                    def __init__(self, product: Product, quantity: int, size: str):
                        self.product = product
                        self.quantity = quantity
                        self.size = size
                
                cart_items = [TempCartItem(
                    product=product,
                    quantity=direct_checkout_data['quantity'],
                    size=direct_checkout_data['size']
                )]
                
                # Calculate totals
                subtotal = product.price * direct_checkout_data['quantity']
                shipping = 10  # Fixed shipping cost
                tax = subtotal * 0.12  # 12% tax
                total = subtotal + shipping + tax
                
            else:
                # Regular cart checkout with eager loading
                cart_items = db_session.query(CartItem)\
                    .filter_by(user_id=current_user.id)\
                    .options(
                        db.joinedload(CartItem.product).joinedload(Product.seller)
                    )\
                    .all()
                
                if not cart_items:
                    flash('Your cart is empty', 'warning')
                    return redirect(url_for('main.cart'))
                
                # Calculate totals
                subtotal = sum(item.product.price * item.quantity for item in cart_items)
                shipping = 10 if subtotal > 0 else 0
                tax = subtotal * 0.12  # 12% tax
                total = subtotal + shipping + tax
            
            # Pre-fill form with user data
            if not form.is_submitted():
                form.full_name.data = current_user.username
                form.phone.data = current_user.phone
                form.email.data = current_user.email
                form.address.data = current_user.address
            
            if request.method == 'POST' and form.validate():
                try:
                    # Create order
                    order = Order(
                        user_id=current_user.id,
                        shipping_address=form.address.data,
                        status='pending',
                        phone=form.phone.data,
                        email=form.email.data,
                        shipping_status='pending',
                        subtotal=subtotal,
                        shipping=shipping,
                        tax=tax,
                        total=total
                    )
                    db_session.add(order)
                    db_session.flush()  # Get order ID
                    
                    if direct_checkout_data:
                        # Check stock availability
                        if product.stock < direct_checkout_data['quantity']:
                            raise ValueError(f"Not enough stock for product {product.id}")
                        
                        # Create order item for direct checkout
                        order_item = OrderItem(
                            order_id=order.id,
                            product_id=product.id,
                            quantity=direct_checkout_data['quantity'],
                            price=product.price,
                            size=direct_checkout_data['size']
                        )
                        db_session.add(order_item)
                        
                        # Update product stock
                        product.stock -= direct_checkout_data['quantity']
                        
                        # Clear direct checkout data
                        session.pop('direct_checkout', None)
                    else:
                        # Process each cart item
                        for item in cart_items:
                            # Check stock availability
                            if item.product.stock < item.quantity:
                                raise ValueError(f"Not enough stock for product {item.product.id}")
                            
                            # Create order item
                            order_item = OrderItem(
                                order_id=order.id,
                                product_id=item.product.id,
                                quantity=item.quantity,
                                price=item.product.price,
                                size=item.size
                            )
                            db_session.add(order_item)
                            
                            # Update product stock
                            item.product.stock -= item.quantity
                        
                        # Clear cart in a single query
                        db_session.query(CartItem).filter_by(user_id=current_user.id).delete()
                    
                    # Send order confirmation email asynchronously
                    try:
                        send_order_confirmation(order)
                    except Exception as email_error:
                        current_app.logger.error(f"Failed to send confirmation email: {str(email_error)}")
                    
                    flash('Order placed successfully!', 'success')
                    return redirect(url_for('main.order_details', order_id=order.id))
                    
                except ValueError as ve:
                    current_app.logger.error(f"Validation error: {str(ve)}")
                    flash(str(ve), 'error')
                    return redirect(url_for('main.checkout'))
                except Exception as e:
                    import traceback
                    current_app.logger.error(f"Error creating order: {str(e)}")
                    current_app.logger.error(f"Traceback: {traceback.format_exc()}")
                    flash('Error processing your order. Please try again.', 'error')
                    return redirect(url_for('main.checkout'))
            elif request.method == 'POST':
                # Form validation failed
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{getattr(form, field).label.text}: {error}", 'error')
            
            return render_template('checkout.html',
                                form=form,
                                cart_items=cart_items,
                                subtotal=subtotal,
                                shipping=shipping,
                                tax=tax,
                                total=total)
                                
    except Exception as e:
        import traceback
        current_app.logger.error(f"Error in checkout route: {str(e)}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        flash('Error processing checkout. Please try again.', 'error')
        return redirect(url_for('main.cart'))

@main.route('/order/<int:order_id>/details')
@login_required
def order_details(order_id: int) -> str:
    try:
        # Get order with eager loading
        order = Order.query.options(
            db.joinedload(Order.items).joinedload(OrderItem.product),
            db.joinedload(Order.user)
        ).get_or_404(order_id)
        
        if order.user_id != current_user.id:
            abort(403)
        
        tracking_updates = []
        if order.tracking_number:
            tracking_updates = ShipmentTracking.query\
                .filter_by(order_id=order.id)\
                .order_by(ShipmentTracking.timestamp.desc())\
                .all()
        
        # Get review status for each order item
        reviewed_items = {
            review.product_id: review 
            for review in Review.query.filter_by(
                user_id=current_user.id,
                order_id=order_id
            ).all()
        }
        
        order_status_colors = {
            'pending': 'warning',
            'processing': 'info',
            'shipped': 'primary',
            'delivered': 'success',
            'cancelled': 'danger',
            'completed': 'success'
        }
        
        return render_template('order_details.html',
                            order=order,
                            tracking_updates=tracking_updates,
                            order_status_colors=order_status_colors,
                            reviewed_items=reviewed_items)
    except Exception as e:
        current_app.logger.error(f"Error in order_details route: {str(e)}")
        flash('Error loading order details. Please try again.', 'error')
        return redirect(url_for('main.orders'))

@main.route('/cart/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_from_cart(product_id: int) -> Dict[str, Any]:
    cart_item = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product_id
    ).first_or_404()
    
    try:
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item removed from cart', 'success')
        return jsonify({'message': 'Item removed successfully'})
    except Exception as e:
        db.session.rollback()
        flash('Error removing item', 'error')
        return jsonify({'error': str(e)}), 500

@main.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id: int) -> Dict[str, Any]:
    try:
        # Get order with row lock
        order = db.session.query(Order).with_for_update().get_or_404(order_id)
        
        # Check if user owns the order
        if order.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
            
        # Check if order can be cancelled (only pending orders)
        if order.status != 'pending':
            return jsonify({'success': False, 'error': 'Only pending orders can be cancelled'}), 400
            
        try:
            # Start a nested transaction
            with db.session.begin_nested():
                # Return items to stock
                for item in order.items:
                    product = db.session.query(Product).with_for_update().get(item.product_id)
                    if product:
                        product.stock += item.quantity
                
                order.status = 'cancelled'
                db.session.flush()
            
            # If we get here, the nested transaction succeeded
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Order cancelled successfully'
            })
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in cancel_order transaction: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Error cancelling order'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error in cancel_order: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error cancelling order'
        }), 500

@main.route('/product/<int:id>')
def product_detail(id: int) -> str:
    product = Product.query.get_or_404(id)
    
    # Get review count and average rating
    reviews_query = Review.query.filter_by(product_id=id)
    review_count = reviews_query.count()
    avg_rating = db.session.query(func.avg(Review.rating))\
        .filter(Review.product_id == id)\
        .scalar() or 0
    
    # Get rating breakdown
    rating_breakdown = {}
    for i in range(5, 0, -1):
        count = Review.query.filter_by(product_id=id, rating=i).count()
        percentage = (count / review_count * 100) if review_count > 0 else 0
        rating_breakdown[i] = {'count': count, 'percentage': percentage}
    
    # Get all reviews with user info
    reviews = Review.query\
        .filter_by(product_id=id)\
        .order_by(Review.created_at.desc())\
        .all()
    
    return render_template('product/detail.html',
                         product=product,
                         avg_rating=avg_rating,
                         review_count=review_count,
                         rating_breakdown=rating_breakdown,
                         reviews=reviews)

@main.route('/order/track/<tracking_number>')
@login_required
def track_order(tracking_number: str) -> str:
    order = Order.query.filter_by(tracking_number=tracking_number).first_or_404()
    
    # Ensure user owns this order
    if order.user_id != current_user.id:
        abort(403)
    
    tracking_updates = ShipmentTracking.query\
        .filter_by(order_id=order.id)\
        .order_by(ShipmentTracking.timestamp.desc())\
        .all()
    
    return render_template('order/tracking.html', 
                         order=order, 
                         tracking_updates=tracking_updates)

@main.route('/product/<int:product_id>/rate', methods=['POST'])
@login_required
def rate_product(product_id: int) -> Dict[str, Any]:
    try:
        product = Product.query.get_or_404(product_id)
        order_id = request.form.get('order_id')
        
        # Verify the order exists and belongs to the user
        order = Order.query.get_or_404(order_id)
        if order.user_id != current_user.id:
            return jsonify({'error': 'Permission denied'}), 403
        
        # Verify the product is in the order
        order_item = OrderItem.query.filter_by(
            order_id=order_id,
            product_id=product_id
        ).first_or_404()
        
        # Check for existing review
        existing_review = Review.query.filter_by(
            user_id=current_user.id,
            product_id=product_id,
            order_id=order_id
        ).first()
        
        if existing_review:
            return jsonify({'error': 'You have already reviewed this product'}), 400
        
        try:
            rating = int(request.form.get('rating'))
            comment = request.form.get('comment')
            
            if not rating or rating < 1 or rating > 5:
                return jsonify({'error': 'Please select a rating between 1 and 5'}), 400
                
            if not comment or not comment.strip():
                return jsonify({'error': 'Please write a review comment'}), 400

            # Create review
            review = Review(
                user_id=current_user.id,
                product_id=product_id,
                order_id=order_id,
                rating=rating,
                comment=comment,
                is_verified_purchase=True
            )
            
            # Handle image uploads
            if 'images[]' in request.files:
                images = request.files.getlist('images[]')
                # Limit to 5 images
                for image in images[:5]:
                    if image and allowed_file(image.filename):
                        # Generate unique filename
                        filename = secure_filename(image.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        
                        # Ensure the upload directory exists
                        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'reviews')
                        os.makedirs(upload_path, exist_ok=True)
                        
                        # Save the image
                        image_path = os.path.join('uploads/reviews', unique_filename)
                        image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], 'reviews', unique_filename))
                        
                        # Create ReviewImage record
                        review_image = ReviewImage(image_path=image_path)
                        review.images.append(review_image)

            # Add review to session
            db.session.add(review)
            
            # Update product rating
            product_reviews = Review.query.filter_by(product_id=product_id).all()
            product_reviews.append(review)  # Include the new review
            if product_reviews:
                total_rating = sum(r.rating for r in product_reviews)
                product.rating = total_rating / len(product_reviews)
                product.review_count = len(product_reviews)
            
            # Update seller rating
            seller = product.seller
            seller_reviews = []
            seller_products = Product.query.filter_by(seller_id=seller.id).all()
            for p in seller_products:
                product_reviews = Review.query.filter_by(product_id=p.id).all()
                seller_reviews.extend(product_reviews)
            
            if seller_reviews:
                total_seller_rating = sum(r.rating for r in seller_reviews)
                seller.rating = round(total_seller_rating / len(seller_reviews), 2)
                seller.review_count = len(seller_reviews)
                print(f"Updated seller rating to {seller.rating} with {seller.review_count} reviews")
            
            # Commit all changes
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Review submitted successfully'
            })
            
        except ValueError:
            return jsonify({'error': 'Invalid rating value'}), 400
            
    except Exception as e:
        db.session.rollback()
        print(f"Error in rate_product: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id: int) -> Dict[str, Any]:
    try:
        product = Product.query.get_or_404(product_id)
        order_id = request.form.get('order_id')
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment')
        
        # Create review object first
        review = Review(
            user_id=current_user.id,
            product_id=product_id,
            order_id=order_id,
            rating=rating,
            comment=comment,
            is_verified_purchase=True
        )
        db.session.add(review)
        
        # Handle image uploads
        if 'images[]' in request.files:
            images = request.files.getlist('images[]')
            for image in images[:5]:  # Limit to 5 images
                if image and allowed_file(image.filename):
                    filename = secure_filename(image.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    
                    # Create upload directory if it doesn't exist
                    upload_path = os.path.join('project', 'static', 'uploads', 'reviews')
                    os.makedirs(upload_path, exist_ok=True)
                    
                    # Save the file
                    image.save(os.path.join(upload_path, unique_filename))
                    
                    # Store relative path in database
                    image_path = f'uploads/reviews/{unique_filename}'
                    review_image = ReviewImage(image_path=image_path)
                    review.images.append(review_image)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@main.route('/checkout/direct/<int:product_id>', methods=['POST'])
@login_required
def direct_checkout(product_id: int) -> Dict[str, Any]:
    try:
        data = request.get_json()
        if not data:
            current_app.logger.error("No JSON data received")
            return jsonify({
                'success': False,
                'message': 'Invalid request data'
            }), 400
            
        quantity = int(data.get('quantity', 1))
        size = data.get('size')
        
        if not size:
            return jsonify({
                'success': False,
                'message': 'Please select a size'
            }), 400
        
        # Get product with eager loading
        product = Product.query.options(
            db.joinedload(Product.seller)
        ).get_or_404(product_id)
        
        # Validate stock
        if quantity > product.stock:
            return jsonify({
                'success': False,
                'message': 'Not enough stock available'
            }), 400
            
        if quantity < 1:
            return jsonify({
                'success': False,
                'message': 'Quantity must be at least 1'
            }), 400
        
        # Store checkout data in session
        session['direct_checkout'] = {
            'product_id': product_id,
            'quantity': quantity,
            'size': size
        }
        
        return jsonify({
            'success': True,
            'redirect_url': url_for('main.checkout')
        })
        
    except ValueError as ve:
        current_app.logger.error(f"Validation error in direct checkout: {str(ve)}")
        return jsonify({
            'success': False,
            'message': str(ve)
        }), 400
    except Exception as e:
        import traceback
        current_app.logger.error(f"Error in direct checkout: {str(e)}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': 'Error processing your request'
        }), 500

@main.route('/contact-user/<int:user_id>', methods=['POST'])
@login_required
def contact_user(user_id: int) -> Dict[str, Any]:
    target_user = User.query.get_or_404(user_id)
    
    subject = request.form.get('subject')
    message = request.form.get('message')
    
    if not subject or not message:
        flash('Please fill in all fields', 'danger')
        return redirect(url_for('main.profile', username=target_user.username))
    
    # Send email notification to the target user
    try:
        msg = Message(
            subject=f"New message from {current_user.username}: {subject}",
            sender=current_user.email,
            recipients=[target_user.email],
            body=f"""
            You have received a new message from {current_user.username}:
            
            Subject: {subject}
            
            Message:
            {message}
            
            You can reply to this email to respond directly.
            """
        )
        mail.send(msg)
        flash('Your message has been sent successfully!', 'success')
    except Exception as e:
        current_app.logger.error(f"Error sending contact email: {str(e)}")
        flash('There was an error sending your message. Please try again later.', 'danger')
    
    return redirect(url_for('main.profile', username=target_user.username))

def init_app(app: Flask) -> None:
    # Initialize Flask-Mail
    mail.init_app(app)
    
    # Register blueprints and other initialization code...
    app.register_blueprint(main)

    @app.context_processor
    def inject_cart_data() -> Dict[str, Any]:
        if current_user.is_authenticated:
            cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
            cart_count = sum(item.quantity for item in cart_items)
            return {'cart_count': cart_count}
        return {'cart_count': 0}
