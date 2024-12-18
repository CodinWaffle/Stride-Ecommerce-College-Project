from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from .models import User, Product, Order, OrderItem, Review, CartItem, Message, ChatMessage, Notification, Follow, OAuth, ReviewImage, ProductSize, ProductImage, FlashSale, ShipmentTracking, Category
from . import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from decimal import Decimal
from functools import wraps
import time
import os
from flask import current_app
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
from slugify import slugify
import traceback

# Create blueprint with url_prefix='/admin'
admin = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """
    Decorator that checks if the current user is an admin.
    Must be used after @login_required
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

# Root route redirects to dashboard
@admin.route('/')
@login_required
@admin_required
def index():
    return redirect(url_for('admin.dashboard'))

@admin.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # Get counts
    total_users = User.query.count()
    total_products = Product.query.count()
    total_orders = Order.query.count()
    
    # Calculate total revenue
    total_revenue = db.session.query(func.sum(Order.total)).scalar() or 0
    
    # Get recent activities (combine recent orders, user registrations, and product updates)
    recent_activities = []
    
    # Add recent orders
    recent_orders = Order.query.order_by(desc(Order.created_at)).limit(5).all()
    for order in recent_orders:
        recent_activities.append({
            'type': 'order',
            'description': f'New order #{order.id} placed by {order.user.email}',
            'timestamp': order.created_at
        })
    
    # Add recent users
    recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()
    for user in recent_users:
        recent_activities.append({
            'type': 'user',
            'description': f'New user registered: {user.email}',
            'timestamp': user.created_at
        })
    
    # Add recent products
    recent_products = Product.query.order_by(desc(Product.created_at)).limit(5).all()
    for product in recent_products:
        recent_activities.append({
            'type': 'product',
            'description': f'New product added: {product.name}',
            'timestamp': product.created_at
        })
    
    # Sort all activities by timestamp
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:10]  # Get only the 10 most recent activities
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_products=total_products,
                         total_orders=total_orders,
                         total_revenue="{:.2f}".format(float(total_revenue)),
                         recent_activities=recent_activities)

@admin.route('/users')
@login_required
@admin_required
def users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@admin.route('/users/toggle_status/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    try:
        # Check if user exists
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Prevent admin from deactivating themselves
        if user.id == current_user.id:
            return jsonify({'success': False, 'message': 'Cannot deactivate your own account'}), 400
        
        # Prevent deactivating other admins
        if user.is_admin:
            return jsonify({'success': False, 'message': 'Cannot deactivate admin accounts'}), 400
        
        # Get current status
        current_status = db.session.execute(
            "SELECT is_active FROM user WHERE id = :user_id",
            {'user_id': user_id}
        ).scalar()
        
        # Toggle the status using raw SQL
        new_status = not current_status if current_status is not None else False
        db.session.execute(
            "UPDATE user SET is_active = :new_status WHERE id = :user_id",
            {'user_id': user_id, 'new_status': new_status}
        )
        
        db.session.commit()
        
        status = 'activated' if new_status else 'deactivated'
        return jsonify({
            'success': True,
            'message': f'User {status} successfully',
            'is_active': new_status
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error toggling user status: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Failed to update user status: {str(e)}'
        }), 500

@admin.route('/products')
@login_required
@admin_required
def products():
    # Get filter parameters
    search_query = request.args.get('search', '').strip()
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    min_stock = request.args.get('min_stock', type=int)
    max_stock = request.args.get('max_stock', type=int)

    # Base query
    query = Product.query.join(User, Product.seller_id == User.id)

    # Apply filters
    if search_query:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search_query}%'),
                Product.description.ilike(f'%{search_query}%')
            )
        )
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if min_stock is not None:
        query = query.filter(Product.stock >= min_stock)
    if max_stock is not None:
        query = query.filter(Product.stock <= max_stock)

    # Execute query with selected columns
    products = query.add_columns(
        Product.id,
        Product.name,
        Product.description,
        Product.price,
        Product.stock,
        Product.image_main,
        User.username.label('seller_name'),
        User.email.label('seller_email')
    ).order_by(Product.created_at.desc()).all()

    return render_template('admin/products.html', 
                        products=products,
                        search_query=search_query,
                        min_price=min_price,
                        max_price=max_price,
                        min_stock=min_stock,
                        max_stock=max_stock)

@admin.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    try:
        # Get categories for the form
        categories = Category.query.all()
        
        # Get the product
        product = Product.query.get_or_404(product_id)
        
        if request.method == 'POST':
            try:
                # Get form data
                name = request.form.get('name')
                description = request.form.get('description')
                price = request.form.get('price')
                stock = request.form.get('stock')
                category_id = request.form.get('category_id')
                
                if not all([name, description, price, stock, category_id]):
                    flash('All fields are required', 'error')
                    return render_template('admin/edit_product.html', product=product, categories=categories)

                try:
                    price = float(price)
                    stock = int(stock)
                    category_id = int(category_id)
                except ValueError:
                    flash('Invalid price, stock, or category value', 'error')
                    return render_template('admin/edit_product.html', product=product, categories=categories)

                # Handle image upload first
                image_path = product.image_main
                if 'image_main' in request.files:
                    file = request.files['image_main']
                    if file and file.filename:
                        try:
                            # Ensure upload directory exists
                            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            # Generate unique filename
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"product_{product_id}_{timestamp}_{secure_filename(file.filename)}"
                            file_path = os.path.join(upload_dir, filename)
                            
                            # Save the file
                            file.save(file_path)
                            
                            # Update image path
                            image_path = 'uploads/products/' + filename
                            
                        except Exception as e:
                            flash(f'Error saving image: {str(e)}', 'error')
                            return render_template('admin/edit_product.html', product=product, categories=categories)

                # Use direct SQL update
                sql = """
                    UPDATE product 
                    SET name = :name,
                        description = :description,
                        price = :price,
                        stock = :stock,
                        category_id = :category_id,
                        slug = :slug,
                        image_main = :image_main,
                        updated_at = :updated_at
                    WHERE id = :product_id
                """
                
                try:
                    db.session.execute(sql, {
                        'name': name,
                        'description': description,
                        'price': price,
                        'stock': stock,
                        'category_id': category_id,
                        'slug': slugify(name),
                        'image_main': image_path,
                        'updated_at': datetime.utcnow(),
                        'product_id': product_id
                    })
                    db.session.commit()
                    flash('Product updated successfully!', 'success')
                    return redirect(url_for('admin.products'))
                except Exception as e:
                    db.session.rollback()
                    flash(f'Database error: {str(e)}', 'error')
                    return render_template('admin/edit_product.html', product=product, categories=categories)
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating product: {str(e)}', 'error')
                return render_template('admin/edit_product.html', product=product, categories=categories)
        
        # GET request - ensure image paths use forward slashes
        if product.image_main:
            product.image_main = product.image_main.replace('\\', '/')
            
        return render_template('admin/edit_product.html', product=product, categories=categories)
        
    except Exception as e:
        flash('An error occurred while processing your request.', 'error')
        return redirect(url_for('admin.products'))

@admin.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    try:
        # Delete related records first using raw SQL with correct table names
        sql_statements = [
            "DELETE FROM product_sizes WHERE product_id = :product_id",
            "DELETE FROM flash_sale WHERE product_id = :product_id",
            "DELETE FROM cart_item WHERE product_id = :product_id",
            "DELETE FROM order_item WHERE product_id = :product_id",
            "DELETE FROM review_image WHERE review_id IN (SELECT id FROM review WHERE product_id = :product_id)",
            "DELETE FROM review WHERE product_id = :product_id",
            "DELETE FROM product_image WHERE product_id = :product_id",
            "DELETE FROM product WHERE id = :product_id"
        ]
        
        # Execute each SQL statement
        for sql in sql_statements:
            try:
                db.session.execute(sql, {'product_id': product_id})
            except Exception as e:
                print(f"Error executing SQL: {sql}")
                print(f"Error message: {str(e)}")
                # Continue with next statement even if this one fails
                continue
        
        db.session.commit()
        flash('Product deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting product: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error deleting product: {str(e)}', 'error')
        
    return redirect(url_for('admin.products'))

@admin.route('/orders')
@login_required
@admin_required
def orders():
    # Get filter parameters
    search_query = request.args.get('search', '').strip()
    status = request.args.get('status')
    min_total = request.args.get('min_total', type=float)
    max_total = request.args.get('max_total', type=float)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Base query
    query = db.session.query(Order).join(User).options(
        db.joinedload(Order.user),
        db.joinedload(Order.items).joinedload(OrderItem.product)
    )

    # Apply filters
    if search_query:
        query = query.filter(
            db.or_(
                Order.id.cast(db.String).like(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%')
            )
        )
    if status:
        query = query.filter(Order.status == status)
    if min_total is not None:
        query = query.filter(Order.total >= min_total)
    if max_total is not None:
        query = query.filter(Order.total <= max_total)
    if start_date:
        query = query.filter(Order.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        # Add one day to include the end date fully
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Order.created_at < end)

    # Get all possible order statuses for the filter dropdown
    statuses = db.session.query(Order.status).distinct().all()
    status_list = [status[0] for status in statuses]

    # Execute query
    orders = query.order_by(Order.created_at.desc()).all()

    # Process orders
    for order in orders:
        order.items_count = len(order.items)
        order.total_items = sum(item.quantity for item in order.items)
        if order.shipping_address:
            order.shipping_address_first_line = order.shipping_address.split('\n')[0]

    return render_template('admin/orders.html', 
                         orders=orders,
                         status_list=status_list,
                         search_query=search_query,
                         selected_status=status,
                         min_total=min_total,
                         max_total=max_total,
                         start_date=start_date,
                         end_date=end_date)

@admin.route('/orders/<int:order_id>')
@login_required
@admin_required
def order_detail(order_id):
    order = Order.query.options(
        db.joinedload(Order.user),
        db.joinedload(Order.items).joinedload(OrderItem.product)
    ).get_or_404(order_id)
    
    # Calculate totals
    order.total_items = sum(item.quantity for item in order.items)
    order.subtotal = sum(item.price * item.quantity for item in order.items)
    
    # Ensure proper image paths
    for item in order.items:
        if item.product and item.product.image_main:
            # Remove any leading slashes and ensure proper path format
            item.product.image_main = item.product.image_main.lstrip('/')
    
    return render_template('admin/order_detail.html', order=order)

@admin.route('/orders/<int:order_id>/update-status', methods=['POST'])
@login_required
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status and new_status in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
        try:
            # Use direct SQL update to avoid session conflicts
            db.session.execute(
                "UPDATE `order` SET status = :status WHERE id = :order_id",
                {'status': new_status, 'order_id': order_id}
            )
            db.session.commit()
            flash('Order status updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating order status: {str(e)}', 'error')
    else:
        flash('Invalid status provided', 'error')
    
    return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/orders/edit/<int:order_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_order(order_id):
    print(f"Editing order {order_id}")
    order = Order.query.options(
        db.joinedload(Order.user),
        db.joinedload(Order.items).joinedload(OrderItem.product)
    ).get_or_404(order_id)
    
    if request.method == 'POST':
        try:
            print("Processing POST request")
            print(f"Form data: {request.form}")
            
            # Update order details
            shipping_address = request.form.get('shipping_address')
            phone = request.form.get('phone')
            print(f"New shipping address: {shipping_address}")
            print(f"New phone: {phone}")
            
            # Update in database using SQL to avoid session issues
            db.session.execute(
                "UPDATE `order` SET shipping_address = :address, phone = :phone WHERE id = :order_id",
                {
                    'address': shipping_address,
                    'phone': phone,
                    'order_id': order_id
                }
            )
            
            # Update order items
            for item in order.items:
                item_id = str(item.id)
                if f'quantity_{item_id}' in request.form:
                    new_quantity = int(request.form.get(f'quantity_{item_id}'))
                    print(f"Updating item {item_id} quantity to {new_quantity}")
                    if new_quantity <= 0:
                        print(f"Deleting item {item_id}")
                        db.session.execute(
                            "DELETE FROM order_item WHERE id = :item_id",
                            {'item_id': item.id}
                        )
                    else:
                        print(f"Updating item {item_id}")
                        db.session.execute(
                            "UPDATE order_item SET quantity = :quantity WHERE id = :item_id",
                            {
                                'quantity': new_quantity,
                                'item_id': item.id
                            }
                        )
            
            # Recalculate order total
            result = db.session.execute(
                """
                SELECT SUM(oi.quantity * oi.price) as subtotal
                FROM order_item oi
                WHERE oi.order_id = :order_id
                """,
                {'order_id': order_id}
            ).first()
            
            subtotal = float(result.subtotal) if result.subtotal else 0
            total = subtotal + order.shipping + order.tax
            
            # Update order totals
            db.session.execute(
                "UPDATE `order` SET subtotal = :subtotal, total = :total WHERE id = :order_id",
                {
                    'subtotal': subtotal,
                    'total': total,
                    'order_id': order_id
                }
            )
            
            db.session.commit()
            print("Changes committed successfully")
            flash('Order updated successfully', 'success')
            return redirect(url_for('admin.order_detail', order_id=order.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error updating order: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            flash(f'Error updating order: {str(e)}', 'error')
            return render_template('admin/edit_order.html', order=order)
    
    return render_template('admin/edit_order.html', order=order)

@admin.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_order(order_id):
    try:
        # Delete order items first
        db.session.execute(
            "DELETE FROM order_item WHERE order_id = :order_id",
            {'order_id': order_id}
        )
        
        # Then delete the order
        db.session.execute(
            "DELETE FROM `order` WHERE id = :order_id",
            {'order_id': order_id}
        )
        
        db.session.commit()
        flash('Order deleted successfully', 'success')
        return redirect(url_for('admin.orders'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting order: {str(e)}', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': 'Cannot delete your own account'}), 400

    try:
        # Check if user exists and is not admin
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
            
        if user.is_admin:
            return jsonify({'success': False, 'message': 'Cannot delete admin accounts'}), 400

        # Execute raw SQL to delete all related data
        sql_statements = [
            # Delete reviews
            "DELETE FROM review WHERE user_id = :user_id",
            
            # Delete cart items
            "DELETE FROM cart_item WHERE user_id = :user_id",
            
            # Delete order items and orders
            "DELETE FROM order_item WHERE order_id IN (SELECT id FROM `order` WHERE user_id = :user_id)",
            "DELETE FROM `order` WHERE user_id = :user_id",
            
            # Delete products
            "DELETE FROM product_images WHERE product_id IN (SELECT id FROM product WHERE seller_id = :user_id)",
            "DELETE FROM flash_sale WHERE product_id IN (SELECT id FROM product WHERE seller_id = :user_id)",
            "DELETE FROM product WHERE seller_id = :user_id",
            
            # Delete messages
            "DELETE FROM message WHERE sender_id = :user_id OR recipient_id = :user_id",
            
            # Delete chat messages
            "DELETE FROM chat_messages WHERE sender_id = :user_id OR recipient_id = :user_id",
            
            # Delete OAuth tokens
            "DELETE FROM flask_dance_oauth WHERE user_id = :user_id",
            
            # Finally, delete the user
            "DELETE FROM user WHERE id = :user_id"
        ]
        
        # Execute each SQL statement
        for sql in sql_statements:
            try:
                db.session.execute(sql, {'user_id': user_id})
                # Commit after each successful deletion
                db.session.commit()
            except Exception as e:
                print(f"Error executing SQL: {sql}")
                print(f"Error message: {str(e)}")
                db.session.rollback()
                # Continue with next statement even if this one fails
                continue
        
        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting user: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Failed to delete user: {str(e)}'
        }), 500