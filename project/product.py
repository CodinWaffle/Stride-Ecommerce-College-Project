import traceback
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, current_app, Response, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from . import db
from .models import Product, Category, Order, OrderItem, User, Review, ProductImage, CartItem, ShipmentTracking, ReviewImage, FlashSale
from slugify import slugify
from sqlalchemy import or_, and_, exists, case, func, String, distinct, cast
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
import csv
import io
import time
import uuid
from flask_wtf.csrf import validate_csrf
import random

product = Blueprint('product', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'project/static/uploads/products')

# Create upload directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@product.route('/seller/dashboard', methods=['GET'])
@login_required
def seller_dashboard():
    if not current_user.is_seller:
        flash('You need a seller account to access this page', 'error')
        return redirect(url_for('main.profile'))
    
    try:
        with db.session.no_autoflush:
            # Get all products with their sales info using subqueries for better performance
            sold_count_subq = (
                db.session.query(
                    OrderItem.product_id,
                    func.sum(OrderItem.quantity).label('sold_count')
                )
                .join(Order)
                .filter(Order.status == 'delivered')
                .group_by(OrderItem.product_id)
                .subquery()
            )

            products_with_sales = (
                db.session.query(
                    Product,
                    func.coalesce(sold_count_subq.c.sold_count, 0).label('sold_count'),
                    Product.stock.label('total_stock')
                )
                .outerjoin(sold_count_subq, Product.id == sold_count_subq.c.product_id)
                .filter(Product.seller_id == current_user.id)
                .all()
            )

            # Calculate sales statistics
            sales_stats = (
                db.session.query(
                    func.coalesce(func.sum(OrderItem.quantity * OrderItem.price), 0).label('total_sales'),
                    func.coalesce(func.avg(Order.total), 0).label('average_order')
                )
                .join(Product, OrderItem.product_id == Product.id)
                .join(Order, OrderItem.order_id == Order.id)
                .filter(
                    Product.seller_id == current_user.id,
                    Order.status == 'delivered'
                )
                .first()
            )

            # Process products data
            all_products = []
            total_stock = 0
            low_stock_products = 0
            
            for product, sold_count, stock in products_with_sales:
                product.sold_count = int(sold_count)
                all_products.append(product)
                total_stock += product.stock
                if product.stock <= 10:
                    low_stock_products += 1

            # Get recent orders with optimized loading
            recent_orders = (
                Order.query
                .options(
                    db.joinedload(Order.items).joinedload(OrderItem.product),
                    db.joinedload(Order.user)
                )
                .join(OrderItem)
                .join(Product)
                .filter(Product.seller_id == current_user.id)
                .order_by(Order.created_at.desc())
                .limit(5)
                .all()
            )

            return render_template(
                'product/seller_dashboard.html',
                total_sales=float(sales_stats.total_sales),
                average_order=float(sales_stats.average_order),
                total_products=len(all_products),
                total_stock=total_stock,
                low_stock_products=low_stock_products,
                recent_orders=recent_orders,
                order_status_colors={
                    'pending': 'warning',
                    'processing': 'info',
                    'shipped': 'primary',
                    'delivered': 'success',
                    'cancelled': 'danger'
                }
            )
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Dashboard error: {str(e)}")
        flash('Error loading dashboard data. Please try again.', 'error')
        return redirect(url_for('main.index'))

@product.route('/seller/products/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if not current_user.is_seller:
        abort(403)
        
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            description = request.form.get('description')
            price = request.form.get('price')
            stock = request.form.get('stock')
            category_id = request.form.get('category_id')
            
            # Validate required fields
            if not all([name, description, price, stock, category_id]):
                flash('All fields are required', 'error')
                return redirect(url_for('product.new_product'))
            
            # Create product first
            product = Product(
                name=name,
                slug=slugify(name),
                price=float(price),
                stock=int(stock),
                description=description,
                category_id=category_id,
                seller_id=current_user.id,
                image_main='img/placeholder.jpg'  # Default image, will be updated if images are uploaded
            )
            db.session.add(product)
            db.session.flush()  # Get product ID
            
            # Handle multiple image uploads
            if 'product_images' in request.files:
                images = request.files.getlist('product_images')
                if len(images) > 5:
                    flash('Maximum 5 images allowed', 'error')
                    return redirect(url_for('product.new_product'))
                
                for index, image in enumerate(images):
                    if image and allowed_file(image.filename):
                        # Create unique filename
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        original_filename = secure_filename(image.filename)
                        filename = f"{slugify(name)}_{timestamp}_{index}_{original_filename}"
                        
                        # Ensure upload directory exists
                        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                        
                        # Save the file
                        file_path = os.path.join(UPLOAD_FOLDER, filename)
                        image.save(file_path)
                        
                        # Store relative path in database
                        db_image_path = f'uploads/products/{filename}'
                        
                        # Create ProductImage record
                        product_image = ProductImage(
                            product_id=product.id,
                            image_path=db_image_path
                        )
                        db.session.add(product_image)
                        
                        # Set first image as main image
                        if index == 0:
                            product.image_main = db_image_path
                        # Set additional images to image_1, image_2, etc.
                        elif index <= 3:  # We have image_1 through image_3
                            setattr(product, f'image_{index}', db_image_path)
            
            db.session.commit()
            flash('Product added successfully!', 'success')
            return redirect(url_for('product.seller_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding product: {str(e)}', 'error')
            
    categories = Category.query.all()
    return render_template('product/create_product.html', categories=categories)

@product.route('/seller/products/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    if not current_user.is_seller:
        abort(403)
    
    try:
        # Get product with row lock if POST request
        if request.method == 'POST':
            product = db.session.query(Product).filter_by(
                id=id, 
                seller_id=current_user.id
            ).with_for_update().first_or_404()
        else:
            product = Product.query.filter_by(
                id=id, 
                seller_id=current_user.id
            ).first_or_404()
        
        if request.method == 'POST':
            try:
                # Start a new database transaction
                with db.session.begin_nested():
                    # Validate and update basic fields
                    name = request.form.get('name')
                    price = request.form.get('price')
                    stock = request.form.get('stock')
                    description = request.form.get('description')
                    category_id = request.form.get('category')
                    
                    if not all([name, price, stock, description, category_id]):
                        flash('All fields are required', 'error')
                        return redirect(url_for('product.edit_product', id=id))
                    
                    # Update product fields
                    product.name = name
                    product.price = float(price)
                    product.stock = int(stock)
                    product.description = description
                    product.category_id = category_id
                    product.slug = slugify(name)
                    
                    # Handle image upload if provided
                    if 'image' in request.files:
                        file = request.files['image']
                        if file and file.filename and allowed_file(file.filename):
                            # Generate unique filename
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"{timestamp}_{secure_filename(file.filename)}"
                            
                            try:
                                # Ensure upload directory exists
                                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                                
                                # Save new image
                                file_path = os.path.join(UPLOAD_FOLDER, filename)
                                file.save(file_path)
                                
                                # Delete old image if it exists and isn't the placeholder
                                if product.image_main and product.image_main != 'img/placeholder.jpg':
                                    try:
                                        old_path = os.path.join(current_app.root_path, 'static', product.image_main)
                                        if os.path.exists(old_path):
                                            os.remove(old_path)
                                    except Exception as e:
                                        current_app.logger.error(f"Error deleting old image: {str(e)}")
                                
                                # Update database path
                                product.image_main = f'uploads/products/{filename}'
                            except Exception as e:
                                current_app.logger.error(f"Error handling image upload: {str(e)}")
                                if 'filename' in locals():
                                    try:
                                        os.remove(os.path.join(UPLOAD_FOLDER, filename))
                                    except:
                                        pass
                                raise
                    
                    # Flush changes to get any database errors before committing
                    db.session.flush()
                
                # If we get here, the nested transaction succeeded
                db.session.commit()
                flash('Product updated successfully!', 'success')
                return redirect(url_for('product.manage_products'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating product: {str(e)}")
                flash(f'Error updating product: {str(e)}', 'error')
                return redirect(url_for('product.edit_product', id=id))
        
        # GET request - render edit form
        categories = Category.query.all()
        return render_template('product/edit_product.html', product=product, categories=categories)
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_product route: {str(e)}")
        flash('Error accessing product', 'error')
        return redirect(url_for('product.manage_products'))

@product.route('/seller/products/<int:id>/delete', methods=['POST'])
@login_required
def delete_product_handler(id):
    if not current_user.is_seller:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    try:
        # Get CSRF token from either headers or form data
        csrf_token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
        if not csrf_token:
            return jsonify({'success': False, 'error': 'Missing CSRF token'}), 400
            
        try:
            validate_csrf(csrf_token)
        except Exception as e:
            return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 400
        
        # Start a new database transaction
        with db.session.begin_nested():
            # Get product with row lock
            product = db.session.query(Product).filter_by(
                id=id, 
                seller_id=current_user.id
            ).with_for_update().first_or_404()
            
            # Check if product has active orders
            has_active_orders = db.session.query(exists().where(
                and_(
                    OrderItem.product_id == id,
                    Order.id == OrderItem.order_id,
                    Order.status.in_(['pending', 'processing', 'shipped'])
                )
            )).scalar()
            
            if has_active_orders:
                return jsonify({
                    'success': False,
                    'error': 'Cannot delete product with active orders'
                }), 400
            
            # Delete product image if it exists and isn't the placeholder
            if product.image_main and product.image_main != 'img/placeholder.jpg':
                try:
                    image_path = os.path.join(current_app.root_path, 'static', product.image_main)
                    if os.path.exists(image_path):
                        os.remove(image_path)
                except Exception as e:
                    current_app.logger.error(f"Error deleting product image: {str(e)}")
            
            # Delete the product
            db.session.delete(product)
            db.session.flush()
        
        # Commit the transaction
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Product deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting product: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error deleting product: {str(e)}'
        }), 500

@product.route('/product/<int:id>')
def product_detail(id):
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
    
    # Get all reviews with user info and images
    reviews = Review.query\
        .options(db.joinedload(Review.user))\
        .options(db.joinedload(Review.images))\
        .filter_by(product_id=id)\
        .order_by(Review.created_at.desc())\
        .all()
    
    return render_template('product/detail.html',
                         product=product,
                         avg_rating=avg_rating,
                         review_count=review_count,
                         rating_breakdown=rating_breakdown,
                         reviews=reviews)

@product.route('/seller/orders')
@login_required
def seller_orders():
    if not current_user.is_seller:
        abort(403)
        
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        search_query = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        date_filter = request.args.get('date', '').strip()
        
        # Build base query with proper joins and eager loading
        base_query = (Order.query
                .join(OrderItem, Order.id == OrderItem.order_id)
                .join(Product, OrderItem.product_id == Product.id)
                .join(User, Order.user_id == User.id)
                .filter(Product.seller_id == current_user.id)
                .options(
                    joinedload(Order.items).joinedload(OrderItem.product),
                    joinedload(Order.user)
                )
                .group_by(Order.id))
        
        # Apply search filter
        if search_query:
            base_query = base_query.filter(
                or_(
                    cast(Order.id, String).ilike(f'%{search_query}%'),
                    User.username.ilike(f'%{search_query}%'),
                    User.email.ilike(f'%{search_query}%')
                )
            )
        
        # Apply status filter
        if status_filter:
            base_query = base_query.filter(Order.status == status_filter)
        
        # Apply date filter
        today = datetime.now().date()
        if date_filter == 'today':
            base_query = base_query.filter(func.date(Order.created_at) == today)
        elif date_filter == 'week':
            base_query = base_query.filter(func.date(Order.created_at) >= today - timedelta(days=7))
        elif date_filter == 'month':
            base_query = base_query.filter(func.date(Order.created_at) >= today - timedelta(days=30))
        
        # Execute pagination with proper ordering
        paginated_orders = base_query.order_by(Order.created_at.desc()).paginate(
            page=page, 
            per_page=per_page,
            error_out=False
        )
        
        if not paginated_orders.items and page > 1:
            abort(404)
        
        # Calculate statistics with a single optimized query
        stats = db.session.query(
            func.count(distinct(Order.id)).label('total_orders'),
            func.sum(case([(Order.status == 'delivered', 1)], else_=0)).label('completed_orders'),
            func.sum(case([(Order.status == 'pending', 1)], else_=0)).label('pending_orders'),
            func.sum(case([(func.date(Order.created_at) == today, 1)], else_=0)).label('today_orders')
        ).select_from(Order).join(
            OrderItem, Order.id == OrderItem.order_id
        ).join(
            Product, OrderItem.product_id == Product.id
        ).filter(
            Product.seller_id == current_user.id
        ).first()
        
        # Prepare template context
        context = {
            'orders': paginated_orders,
            'total_orders': stats.total_orders or 0,
            'completed_orders': stats.completed_orders or 0,
            'pending_orders': stats.pending_orders or 0,
            'today_orders': stats.today_orders or 0,
            'search_query': search_query,
            'status_filter': status_filter,
            'date_filter': date_filter,
            'status_colors': {
                'pending': 'warning',
                'processing': 'info',
                'shipped': 'primary',
                'delivered': 'success',
                'cancelled': 'danger'
            }
        }
        
        return render_template('product/seller_orders.html', **context)
                           
    except Exception as e:
        db.session.rollback()
        print(f"Error in seller_orders: {str(e)}")
        print(traceback.format_exc())
        flash('Error loading orders. Please try again.', 'error')
        return redirect(url_for('product.seller_dashboard'))

@product.route('/seller/orders/<int:order_id>/details')
@login_required
def seller_order_details(order_id):
    if not current_user.is_seller:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        # Optimize order query with proper joins
        order = (Order.query
                .options(
                    db.joinedload(Order.items).joinedload(OrderItem.product),
                    db.joinedload(Order.user)
                )
                .filter(Order.id == order_id)
                .first())
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
            
        # Filter items to only show products from this seller
        seller_items = [item for item in order.items if item.product and item.product.seller_id == current_user.id]
        
        if not seller_items:
            return jsonify({'error': 'No items found for this seller'}), 403
        
        # Calculate order totals for seller's items only
        subtotal = sum(item.price * item.quantity for item in seller_items)
        shipping = 10.00  # Fixed shipping cost
        total = subtotal + shipping
        
        # Status colors for badges
        status_colors = {
            'pending': 'warning',
            'processing': 'info',
            'shipped': 'primary',
            'delivered': 'success',
            'cancelled': 'danger'
        }
        
        context = {
            'order': order,
            'order_items': seller_items,
            'status_colors': status_colors,
            'subtotal': subtotal,
            'shipping': shipping,
            'total': total
        }
        
        html = render_template('product/order_details_content.html', **context)
        if not html.strip():
            return jsonify({'error': 'Error rendering template'}), 500
            
        response = make_response(html)
        response.headers['Content-Type'] = 'text/html'
        return response
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product.route('/seller/orders/<int:order_id>/update', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_seller:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        # Get the order with a fresh query and lock
        order = db.session.query(Order).filter_by(id=order_id).with_for_update().first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Verify seller ownership
        seller_items = db.session.query(OrderItem).join(Product).filter(
            OrderItem.order_id == order_id,
            Product.seller_id == current_user.id
        ).first()
        
        if not seller_items:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get and validate new status
        new_status = request.form.get('status')
        if not new_status or new_status not in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
            return jsonify({'error': 'Invalid status value'}), 400
        
        # Update the order
        order.status = new_status
        order.updated_at = datetime.now()
        
        # Save changes
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Order status updated successfully',
            'new_status': new_status
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating order status: {str(e)}")
        return jsonify({'error': 'Failed to update order status'}), 500

@product.route('/seller/products/<int:id>/stock', methods=['POST'])
@login_required
def update_stock(id):
    if not current_user.is_seller:
        abort(403)
        
    product = Product.query.get_or_404(id)
    if product.seller_id != current_user.id:
        abort(403)
        
    try:
        new_stock = int(request.form.get('stock', 0))
        if new_stock < 0:
            return jsonify({'error': 'Stock cannot be negative'}), 400
            
        product.stock = new_stock
        db.session.commit()
        return jsonify({'success': True})
    except ValueError:
        return jsonify({'error': 'Invalid stock value'}), 400
    except:
        db.session.rollback()
        return jsonify({'error': 'Error updating stock'}), 500

@product.route('/seller/products/export')
@login_required
def export_products():
    if not current_user.is_seller:
        abort(403)
        
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['name', 'description', 'price', 'stock', 'category'])
    
    # Write products
    products = Product.query.filter_by(seller_id=current_user.id).all()
    for product in products:
        writer.writerow([
            product.name,
            product.description,
            product.price,
            product.stock,
            product.category.name
        ])
    
    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=products.csv'}
    )

@product.route('/seller/products/import', methods=['POST'])
@login_required
def import_products():
    if not current_user.is_seller:
        abort(403)
        
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
        
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"))
        reader = csv.DictReader(stream)
        
        for row in reader:
            category = Category.query.filter_by(name=row['category']).first()
            if not category:
                continue
                
            product = Product(
                name=row['name'],
                description=row['description'],
                price=float(row['price']),
                stock=int(row['stock']),
                category_id=category.id,
                seller_id=current_user.id
            )
            db.session.add(product)
            
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product.route('/product/<int:id>/quick-view')
def quick_view(id):
    product = Product.query.get_or_404(id)
    return jsonify({
        'id': product.id,
        'name': product.name,
        'price': float(product.price),
        'description': product.description,
        'stock': product.stock,
        'image_url': url_for('static', filename=product.image_main)
    })

@product.route('/product/<int:id>/review', methods=['POST'])
@login_required
def add_review(id):
    try:
        # Existing validation code...
        
        # Handle image uploads
        uploaded_images = request.files.getlist('images[]')
        image_paths = []
        
        for image in uploaded_images:
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                filepath = os.path.join('uploads/reviews', unique_filename)
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filepath)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Save image
                image.save(full_path)
                image_paths.append(filepath)

        # Create review
        review = Review(
            user_id=current_user.id,
            product_id=id,
            order_id=request.form.get('order_id'),
            rating=int(request.form.get('rating')),
            comment=request.form.get('comment').strip(),
            is_verified_purchase=True
        )
        
        # Add review images
        for path in image_paths:
            review_image = ReviewImage(image_path=path)
            review.images.append(review_image)
        
        db.session.add(review)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Review submitted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@product.route('/product/review/<int:id>/delete', methods=['POST'])
@login_required
def delete_review(id):
    review = Review.query.get_or_404(id)
    
    # Check if the review belongs to one of the seller's products
    if review.product.seller_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        db.session.delete(review)
        db.session.commit()
        return jsonify({'message': 'Review deleted successfully'})
    except:
        db.session.rollback()
        return jsonify({'error': 'Error deleting review'}), 500

@product.route('/seller/reviews/filter')
@login_required
def filter_reviews():
    rating = request.args.get('rating', 'all')
    sort = request.args.get('sort', 'newest')
    response_status = request.args.get('response', 'all')
    
    query = Review.query.join(Product).filter(Product.seller_id == current_user.id)
    
    if rating != 'all':
        query = query.filter(Review.rating == int(rating))
        
    if response_status == 'responded':
        query = query.filter(Review.seller_response.isnot(None))
    elif response_status == 'pending':
        query = query.filter(Review.seller_response.is_(None))
    
    if sort == 'newest':
        query = query.order_by(Review.created_at.desc())
    elif sort == 'oldest':
        query = query.order_by(Review.created_at.asc())
    elif sort == 'highest':
        query = query.order_by(Review.rating.desc())
    elif sort == 'lowest':
        query = query.order_by(Review.rating.asc())
    
    reviews = query.all()
    
    return jsonify({
        'reviews': [{
            'id': r.id,
            'product_name': r.product.name,
            'product_image': r.product.image_main,
            'rating': r.rating,
            'comment': r.comment,
            'user_name': r.user.name,
            'created_at': r.created_at.strftime('%B %d, %Y'),
            'seller_response': r.seller_response,
            'response_date': r.response_date.strftime('%B %d, %Y') if r.response_date else None
        } for r in reviews]
    })

@product.route('/seller/review/<int:review_id>/details')
@login_required
def get_review_details(review_id):
    print(f"\n=== Getting review details for review {review_id} ===")
    print(f"Current user ID: {current_user.id}")
    
    if not current_user.is_seller:
        print("Access denied: User is not a seller")
        return jsonify({'error': 'Permission denied'}), 403
        
    try:
        # Get review with all related data
        review = (Review.query
                 .options(db.joinedload(Review.user))
                 .options(db.joinedload(Review.product))
                 .filter_by(id=review_id)
                 .first())
        
        if not review:
            print(f"Review {review_id} not found")
            return jsonify({'error': 'Review not found'}), 404
            
        # Verify the review is for one of the seller's products
        if review.product.seller_id != current_user.id:
            print(f"Review {review_id} does not belong to seller {current_user.id}")
            return jsonify({'error': 'Permission denied'}), 403
            
        print(f"Found review. Product: {review.product.name}, User: {review.user.username}")
        print(f"Rating: {review.rating}, Has response: {bool(review.seller_response)}")
            
        # Render review details template
        return render_template('product/review_details.html',
                           review=review,
                           product=review.product,
                           user=review.user)
                           
    except Exception as e:
        print(f"Error getting review details: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to load review details'}), 500

@product.route('/seller/review/<int:id>/respond', methods=['POST'])
@login_required
def respond_to_review(id):
    print(f"\n=== Responding to review {id} ===")
    print(f"Current user ID: {current_user.id}")
    print(f"Form data: {request.form}")
    
    if not current_user.is_seller:
        print("Access denied: User is not a seller")
        return jsonify({
            'success': False,
            'error': 'Permission denied'
        }), 403
        
    try:
        # Get review with product data
        review = Review.query.options(db.joinedload(Review.product)).get(id)
        if not review:
            print(f"Review {id} not found")
            return jsonify({
                'success': False,
                'error': 'Review not found'
            }), 404
            
        # Verify the review is for one of the seller's products
        if review.product.seller_id != current_user.id:
            print(f"Review {id} does not belong to seller {current_user.id}")
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
            
        # Check if review already has a response
        if review.seller_response:
            print(f"Review {id} already has a response")
            return jsonify({
                'success': False,
                'error': 'This review already has a response'
            }), 400
            
        # Get response text
        response_text = request.form.get('response')
        if not response_text:
            print("No response text provided")
            return jsonify({
                'success': False,
                'error': 'Response text is required'
            }), 400
            
        print(f"Adding response to review {id}")
        # Update review with seller's response
        review.seller_response = response_text
        review.response_date = datetime.utcnow()
        
        db.session.commit()
        print("Response added successfully")
        
        return jsonify({
            'success': True,
            'message': 'Response submitted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error responding to review: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Failed to submit response: {str(e)}'
        }), 500

@product.route('/seller/product/<int:product_id>/toggle-featured', methods=['POST'])
@login_required
def toggle_featured(product_id):
    product = Product.query.filter_by(id=product_id, seller_id=current_user.id).first_or_404()
    
    try:
        product.is_featured = not product.is_featured
        db.session.commit()
        return jsonify({
            'status': 'success',
            'is_featured': product.is_featured
        })
    except:
        db.session.rollback()
        return jsonify({'error': 'Error updating product'}), 500

@product.route('/seller/product/<int:product_id>/update-stock', methods=['POST'])
@login_required
def update_product_stock(product_id):
    product = Product.query.filter_by(id=product_id, seller_id=current_user.id).first_or_404()
    
    try:
        data = request.get_json()
        new_stock = int(data.get('stock', 0))
        if new_stock < 0:
            return jsonify({'error': 'Stock cannot be negative'}), 400
            
        product.stock = new_stock
        db.session.commit()
        return jsonify({'status': 'success'})
    except:
        db.session.rollback()
        return jsonify({'error': 'Error updating stock'}), 500

@product.route('/seller/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if not current_user.is_seller:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    # Define icons mapping
    icons = {
        'Sneakers': 'fa-shoe-prints',
        'Running': 'fa-running',
        'Basketball': 'fa-basketball',
        'Casual': 'fa-walking',
        'Sports': 'fa-futbol',
        'Training': 'fa-dumbbell',
        'Lifestyle': 'fa-star',
        'Limited Edition': 'fa-crown',
        'Kids': 'fa-child',
        'Sale': 'fa-tag'
    }
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        slug = slugify(name)
        
        try:
            existing_category = Category.query.filter_by(name=name).first()
            if existing_category:
                return jsonify({
                    'success': False, 
                    'error': 'Category with this name already exists.'
                })

            category = Category(
                name=name,
                description=description,
                slug=slug
            )
            db.session.add(category)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False, 
                'error': str(e)
            })
    
    categories = Category.query.all()
    return render_template('product/categories.html', categories=categories, icons=icons)

@product.route('/seller/products/<int:id>/images', methods=['POST'])
@login_required
def manage_product_images(id):
    if not current_user.is_seller:
        abort(403)
        
    product = Product.query.filter_by(id=id, seller_id=current_user.id).first_or_404()
    
    if 'images' not in request.files:
        flash('No images uploaded', 'error')
        return redirect(url_for('product.edit_product', id=id))
        
    images = request.files.getlist('images')
    uploaded_images = []
    
    for image in images:
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            image.save(file_path)
            
            product_image = ProductImage(
                product_id=product.id,
                image_path=f'uploads/products/{filename}'
            )
            db.session.add(product_image)
            uploaded_images.append(product_image)
    
    try:
        db.session.commit()
        flash(f'{len(uploaded_images)} images uploaded successfully', 'success')
    except:
        db.session.rollback()
        flash('Error uploading images', 'error')
    
    return redirect(url_for('product.edit_product', id=id))

@product.route('/seller/products/<int:id>/archive', methods=['POST'])
@login_required
def archive_product(id):
    if not current_user.is_seller:
        abort(403)
    
    product = Product.query.filter_by(id=id, seller_id=current_user.id).first_or_404()
    
    try:
        product.is_archived = not product.is_archived
        db.session.commit()
        return jsonify({'success': True})
    except:
        db.session.rollback()
        return jsonify({'success': False}), 500

@product.route('/seller/product/<int:product_id>/toggle-archive', methods=['POST'])
@login_required
def toggle_archive_product(product_id):
    if not current_user.is_seller:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    
    product = Product.query.filter_by(id=product_id, seller_id=current_user.id).first_or_404()
    
    try:
        product.is_archived = not product.is_archived
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@product.route('/seller/products/<int:product_id>/toggle-status', methods=['POST'])
@login_required
def toggle_product_status(product_id):
    if not current_user.is_seller:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    try:
        # Get CSRF token from either headers or form data
        csrf_token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
        if not csrf_token:
            return jsonify({'success': False, 'error': 'Missing CSRF token'}), 400
            
        try:
            validate_csrf(csrf_token)
        except Exception as e:
            return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 400
        
        # Start a new database transaction
        with db.session.begin_nested():
            # Get product with row lock
            product = db.session.query(Product).filter_by(
                id=product_id, 
                seller_id=current_user.id
            ).with_for_update().first_or_404()
            
            # Toggle the status
            product.is_active = not product.is_active
            db.session.flush()  # Flush changes to get the updated status
            
            # Prepare response data
            response_data = {
                'success': True,
                'message': f'Product {"activated" if product.is_active else "deactivated"} successfully',
                'is_active': product.is_active
            }
        
        # Commit the transaction
        db.session.commit()
        
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling product status: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error updating product status: {str(e)}'
        }), 500

@product.route('/seller/analytics', methods=['GET'])
@login_required
def get_analytics():
    if not current_user.is_seller:
        abort(403)
    
    try:
        period = request.args.get('period', 'weekly')
        today = datetime.now()
        current_app.logger.info(f"\nAnalytics request - Period: {period}")
        current_app.logger.info(f"Current user ID: {current_user.id}")
        
        # Check for test_mode parameter
        if request.args.get('test_mode') == 'true':
            # Create a test order
            product = Product.query.filter_by(seller_id=current_user.id).first()
            if product:
                order = Order(
                    user_id=current_user.id,
                    status='delivered',
                    total=product.price,
                    subtotal=product.price,
                    shipping=0,
                    tax=0,
                    shipping_address='Test Address',
                    phone='1234567890',
                    email=current_user.email,
                    created_at=datetime.now()
                )
                db.session.add(order)
                db.session.flush()
                
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=1,
                    price=product.price
                )
                db.session.add(order_item)
                db.session.commit()
                current_app.logger.info("Created test order successfully")
        
        if period == 'weekly':
            start_date = today - timedelta(days=6)
            label_format = '%a'
        elif period == 'monthly':
            start_date = today - timedelta(days=29)
            label_format = '%b %d'
        else:  # yearly
            start_date = today - timedelta(days=364)
            label_format = '%b'
        
        # Query sales data
        sales_data = db.session.query(
            func.date(Order.created_at).label('date'),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.price), 0).label('total')
        ).join(
            OrderItem, Order.id == OrderItem.order_id
        ).join(
            Product, OrderItem.product_id == Product.id
        ).filter(
            Product.seller_id == current_user.id,
            Order.status == 'delivered',
            Order.created_at.between(start_date, today)
        ).group_by(
            func.date(Order.created_at)
        ).order_by(
            func.date(Order.created_at)
        ).all()

        current_app.logger.info(f"Found {len(sales_data)} days with sales")
        for sale in sales_data:
            current_app.logger.info(f"Date: {sale.date}, Total: {sale.total}")

        # Create a map of dates to sales
        sales_map = {sale.date: sale.total for sale in sales_data}
        
        # Generate labels and values for all days
        labels = []
        values = []
        current_date = start_date

        while current_date <= today:
            current_date_only = current_date.date()
            labels.append(current_date_only.strftime(label_format))
            values.append(sales_map.get(current_date_only, 0))
            current_date += timedelta(days=1)

        return jsonify({
            'labels': labels,
            'values': values
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in analytics endpoint: {str(e)}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        db.session.rollback()
        return jsonify({'error': 'Failed to fetch analytics data'}), 500

@product.route('/seller/categories/<int:id>', methods=['GET'])
@login_required
def get_category(id):
    if not current_user.is_seller:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        category = Category.query.get_or_404(id)
        return jsonify({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'slug': category.slug
        })
    except Exception as e:
        current_app.logger.error(f"Error getting category: {str(e)}")
        return jsonify({'error': 'Failed to get category details'}), 500

@product.route('/seller/categories/<int:id>/update', methods=['POST'])
@login_required
def update_category(id):
    if not current_user.is_seller:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        # Get category with row lock to prevent concurrent updates
        category = db.session.query(Category).filter_by(id=id).with_for_update().first_or_404()
        
        # Get form data
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Validate input
        if not name:
            return jsonify({'error': 'Category name is required'}), 400
            
        # Check if name is already taken by another category
        existing_category = Category.query.filter(
            Category.name == name,
            Category.id != id
        ).first()
        if existing_category:
            return jsonify({'error': 'A category with this name already exists'}), 400
        
        # Update category within a nested transaction
        with db.session.begin_nested():
            category.name = name
            category.description = description
            category.slug = slugify(name)
            db.session.flush()  # Flush changes to detect any database errors
        
        # If we get here, the nested transaction succeeded
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Category updated successfully',
            'category': {
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'slug': category.slug
            }
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating category: {str(e)}")
        return jsonify({'error': 'Failed to update category'}), 500

@product.route('/seller/categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_category_by_id(id):
    if not current_user.is_seller:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    try:
        # Get category with row lock
        category = db.session.query(Category).filter_by(id=id).with_for_update().first()
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        # Check if category has products
        product_count = db.session.query(Product).filter_by(category_id=id).count()
        if product_count > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot delete category. {product_count} products are using this category.'
            }), 400

        # Delete the category
        db.session.delete(category)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Category "{category.name}" deleted successfully'
        })
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting category {id}: {str(e)}")
        current_app.logger.error(f"Error type: {type(e)}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@product.route('/seller/categories/list')
@login_required
def list_categories():
    if not current_user.is_seller:
        return jsonify({'error': 'Access denied'}), 403
    
    categories = Category.query.all()
    return jsonify([{
        'id': category.id,
        'name': category.name
    } for category in categories])

@product.route('/seller/products/list')
@login_required
def list_products():
    if not current_user.is_seller:
        return jsonify({'error': 'Access denied'}), 403
    
    products = Product.query.filter_by(seller_id=current_user.id).all()
    return jsonify({
        'success': True,
        'products': [{
            'id': p.id,
            'name': p.name,
            'price': float(p.price),
            'stock': p.stock,
            'is_active': p.is_active,
            'image_main': url_for('static', filename=p.image_main),
            'category': {
                'id': p.category.id,
                'name': p.category.name
            } if p.category else None
        } for p in products]
    })

@product.route('/seller/products/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_product_activation(id):
    if not current_user.is_seller:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
        
    try:
        product = Product.query.get_or_404(id)
        
        if product.seller_id != current_user.id:
            return jsonify({'success': False, 'error': 'Permission denied'}), 403
            
        product.is_active = not product.is_active
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Product {"activated" if product.is_active else "deactivated"} successfully',
            'is_active': product.is_active
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@product.route('/seller/<username>')
def seller_store(username):
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort = request.args.get('sort', 'newest')
    
    # Get seller
    seller = User.query.filter_by(username=username, is_seller=True).first_or_404()
    
    # Calculate total reviews and average rating across all seller's products
    reviews = []
    total_rating = 0
    for product in seller.products:
        product_reviews = Review.query.filter_by(product_id=product.id).all()
        reviews.extend(product_reviews)
        total_rating += sum(review.rating for review in product_reviews)
    
    review_count = len(reviews)
    avg_rating = total_rating / review_count if review_count > 0 else 0
    
    # Base query for products
    query = Product.query.filter_by(seller_id=seller.id)
    
    # Apply filters and sorting (existing code remains the same)
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))
    
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    
    if sort == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_high':
        query = query.order_by(Product.price.desc())
    else:  # newest
        query = query.order_by(Product.created_at.desc())
    
    products = query.paginate(page=page, per_page=12, error_out=False)
    
    return render_template('product/seller_store.html',
                         seller=seller,
                         products=products,
                         total_products=query.count(),
                         avg_rating=avg_rating,
                         review_count=review_count)

@product.route('/seller/profile/update', methods=['POST'])
@login_required
def update_seller_profile():
    if not current_user.is_seller:
        abort(403)
        
    try:
        user = User.query.get(current_user.id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Handle profile image upload
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"profile_{user.id}_{int(time.time())}_{filename}"
                
                # Create upload directory if it doesn't exist
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Save the file
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                
                # Update database path - make sure path matches profile.html expectation
                user.profile_image = f'uploads/profiles/{filename}'

        # Update store information
        user.store_name = request.form.get('store_name', user.store_name)
        user.store_description = request.form.get('store_description', user.store_description)
        
        db.session.add(user)
        db.session.commit()
        return jsonify({'message': 'Profile updated successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@product.route('/product/<int:id>/reviews')
def get_reviews(id):
    sort = request.args.get('sort', 'latest')
    
    query = Review.query.filter_by(product_id=id)
    
    if sort == 'latest':
        query = query.order_by(Review.created_at.desc())
    elif sort == 'highest':
        query = query.order_by(Review.rating.desc())
    elif sort == 'lowest':
        query = query.order_by(Review.rating.asc())
    
    reviews = query.all()
    
    return jsonify({
        'reviews': [{
            'id': r.id,
            'user': {
                'username': r.user.username,
                'avatar': r.user.avatar
            },
            'rating': r.rating,
            'comment': r.comment,
            'media': r.media,
            'created_at': r.created_at.strftime('%B %d, %Y'),
            'seller_response': r.seller_response,
            'response_date': r.response_date.strftime('%B %d, %Y') if r.response_date else None
        } for r in reviews]
    })

@product.route('/seller/order/<int:order_id>/tracking', methods=['POST'])
@login_required
def update_tracking(order_id):
    if not current_user.is_seller:
        abort(403)
        
    order = Order.query.get_or_404(order_id)
    
    # Verify seller owns the product in this order
    order_products = [item.product.seller_id for item in order.items]
    if current_user.id not in order_products:
        abort(403)
    
    try:
        tracking = ShipmentTracking(
            order_id=order_id,
            status=request.form.get('status'),
            location=request.form.get('location'),
            description=request.form.get('description'),
            tracking_number=request.form.get('tracking_number'),
            courier=request.form.get('courier')
        )
        
        # Update order tracking info if provided
        if request.form.get('tracking_number'):
            order.tracking_number = request.form.get('tracking_number')
            order.courier = request.form.get('courier')
            order.shipping_status = request.form.get('status')
            
        db.session.add(tracking)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product.route('/seller/create-test-order', methods=['POST'])
@login_required
def create_test_order():
    if not current_user.is_seller:
        abort(403)
    
    try:
        # Get a product from the current seller
        product = Product.query.filter_by(seller_id=current_user.id).first()
        if not product:
            return jsonify({'error': 'No products found for seller'}), 404
        
        # Create a test order
        order = Order(
            user_id=current_user.id,
            status='delivered',
            total=product.price,
            subtotal=product.price,
            shipping=0,
            tax=0,
            shipping_address='Test Address',
            phone='1234567890',
            email=current_user.email,
            created_at=datetime.now()
        )
        db.session.add(order)
        db.session.flush()
        
        # Create order item
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            price=product.price
        )
        db.session.add(order_item)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Test order created successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product.route('/seller/products', methods=['GET'])
@login_required
def manage_products():
    if not current_user.is_seller:
        flash('You need a seller account to access this page', 'error')
        return redirect(url_for('main.profile'))
    
    try:
        # Get query parameters with proper type conversion and defaults
        page = max(1, request.args.get('page', 1, type=int))
        search = request.args.get('search', '').strip()
        category_filter = request.args.get('category', None, type=int)
        stock_filter = request.args.get('stock', None)
        sort = request.args.get('sort', 'newest')
        
        # Create subquery for sold count
        sold_count_subq = (
            db.session.query(
                OrderItem.product_id,
                func.sum(OrderItem.quantity).label('sold_count')
            )
            .join(Order)
            .filter(Order.status == 'delivered')
            .group_by(OrderItem.product_id)
            .subquery()
        )
        
        # Create subquery for active orders
        active_orders_subq = (
            db.session.query(OrderItem.product_id)
            .join(Order)
            .filter(Order.status.in_(['pending', 'processing', 'shipped']))
            .group_by(OrderItem.product_id)
            .subquery()
        )
        
        # Base query with optimized loading
        query = (
            Product.query
            .options(
                db.joinedload(Product.category),
                db.lazyload('*')  # Disable other relationship loading
            )
            .outerjoin(sold_count_subq, Product.id == sold_count_subq.c.product_id)
            .outerjoin(active_orders_subq, Product.id == active_orders_subq.c.product_id)
            .add_columns(
                func.coalesce(sold_count_subq.c.sold_count, 0).label('sold_count'),
                (active_orders_subq.c.product_id != None).label('has_active_orders')
            )
            .filter(Product.seller_id == current_user.id)
        )

        # Apply search filter with proper error handling
        if search:
            try:
                search_filter = or_(
                    Product.name.ilike(f'%{search}%'),
                    Product.description.ilike(f'%{search}%')
                )
                query = query.filter(search_filter)
            except Exception as e:
                current_app.logger.error(f"Error applying search filter: {str(e)}")
                flash('Error applying search filter. Please try again.', 'error')
                return redirect(url_for('product.manage_products'))
        
        # Apply category filter
        if category_filter:
            query = query.filter(Product.category_id == category_filter)
            
        # Apply stock filter
        if stock_filter == 'low':
            query = query.filter(Product.stock <= 10, Product.stock > 0)
        elif stock_filter == 'out':
            query = query.filter(Product.stock == 0)
        
        # Apply sorting with proper error handling
        sort_options = {
            'name_asc': Product.name.asc(),
            'name_desc': Product.name.desc(),
            'price_low': Product.price.asc(),
            'price_high': Product.price.desc(),
            'stock_low': Product.stock.asc(),
            'stock_high': Product.stock.desc(),
            'newest': Product.created_at.desc()
        }
        query = query.order_by(sort_options.get(sort, sort_options['newest']))

        # Get statistics with optimized single query
        try:
            stats_query = (
                db.session.query(
                    func.count(Product.id).label('total_products'),
                    func.sum(case([(Product.is_active == True, 1)], else_=0)).label('active_products'),
                    func.sum(case([(and_(Product.stock <= 10, Product.stock > 0), 1)], else_=0)).label('low_stock'),
                    func.sum(case([(Product.stock == 0, 1)], else_=0)).label('out_of_stock'),
                    func.sum(Product.stock).label('total_stock')
                )
                .filter(Product.seller_id == current_user.id)
                .first()
            )
        except Exception as e:
            current_app.logger.error(f"Error fetching stats: {str(e)}")
            stats_query = None

        # Get categories with error handling
        try:
            categories = Category.query.all()
        except Exception as e:
            current_app.logger.error(f"Error fetching categories: {str(e)}")
            categories = []

        # Paginate results with error handling
        try:
            pagination = query.paginate(page=page, per_page=12, error_out=False)
            if not pagination.items and page > 1:
                return redirect(url_for('product.manage_products', page=1))
        except Exception as e:
            current_app.logger.error(f"Error paginating products: {str(e)}")
            flash('Error loading products. Please try again.', 'error')
            return redirect(url_for('product.seller_dashboard'))

        # Process stats with proper null handling
        stats = {
            'total_products': getattr(stats_query, 'total_products', 0) or 0,
            'active_products': getattr(stats_query, 'active_products', 0) or 0,
            'low_stock': getattr(stats_query, 'low_stock', 0) or 0,
            'out_of_stock': getattr(stats_query, 'out_of_stock', 0) or 0,
            'total_stock': getattr(stats_query, 'total_stock', 0) or 0
        }
        
        return render_template(
            'product/manage_products.html',
            products=pagination.items,
            pagination=pagination,
            categories=categories,
            stats=stats,
            search=search,
            category_filter=category_filter,
            stock_filter=stock_filter,
            sort=sort
        )
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in manage_products: {str(e)}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        flash('Error loading products. Please try again.', 'error')
        return redirect(url_for('product.seller_dashboard'))

@product.route('/create', methods=['GET', 'POST'])
@login_required
def create_product():
    if not current_user.is_seller:
        flash('You need a seller account to create products.', 'danger')
        return redirect(url_for('main.profile'))

    categories = Category.query.all()
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            description = request.form.get('description')
            price = request.form.get('price')
            stock = request.form.get('stock')
            category_id = request.form.get('category_id')
            
            # Validate required fields
            if not all([name, description, price, stock, category_id]):
                missing_fields = [field for field, value in {
                    'name': name,
                    'description': description,
                    'price': price,
                    'stock': stock,
                    'category_id': category_id
                }.items() if not value]
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                flash(error_msg, 'danger')
                return redirect(url_for('product.create_product'))

            try:
                price = float(price)
                stock = int(stock)
                category_id = int(category_id)
            except ValueError as e:
                error_msg = f"Invalid value format: {str(e)}"
                flash(error_msg, 'danger')
                return redirect(url_for('product.create_product'))

            # Create new product
            product = Product(
                name=name,
                description=description,
                price=price,
                stock=stock,
                category_id=category_id,
                seller_id=current_user.id,
                slug=slugify(name),
                image_main='img/placeholder.jpg'  # Default image path
            )
            
            # Add product to session first
            db.session.add(product)
            db.session.flush()  # This assigns an ID to the product
            
            # Handle main product image
            if 'product_images' in request.files:
                files = request.files.getlist('product_images')
                first_image = True
                
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        try:
                            # Generate unique filename
                            filename = secure_filename(file.filename)
                            timestamp = time.strftime("%Y%m%d_%H%M%S")
                            unique_filename = f"{slugify(name)}_{timestamp}_{filename}"
                            
                            # Ensure upload directory exists
                            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                            
                            # Save file
                            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                            file.save(file_path)
                            image_path = f'uploads/products/{unique_filename}'
                            
                            # First image becomes the main image
                            if first_image:
                                product.image_main = image_path
                                first_image = False
                            else:
                                # Additional images go to product_images
                                product_image = ProductImage(
                                    product_id=product.id,  # Now we have the product ID
                                    image_path=image_path
                                )
                                db.session.add(product_image)
                            
                            current_app.logger.info(f"Image saved: {file_path}")
                        except Exception as e:
                            db.session.rollback()
                            current_app.logger.error(f"Error saving image: {str(e)}")
                            flash(f"Error saving image: {str(e)}", 'danger')
                            return redirect(url_for('product.create_product'))

            # Save everything
            db.session.commit()
            flash('Product created successfully!', 'success')
            return redirect(url_for('product.manage_products'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating product: {str(e)}")
            flash(f'Error creating product: {str(e)}', 'danger')
            return redirect(url_for('product.create_product'))
    
    return render_template('product/create_product.html', categories=categories)

@product.route('/seller/verify', methods=['GET'])
@login_required
def verify_seller():
    try:
        if not current_user.is_seller:
            return jsonify({'error': 'Not a seller'}), 403
            
        # Check if seller has completed registration
        if not current_user.store_name or not current_user.store_description:
            return jsonify({'error': 'Please complete your seller profile'}), 403
            
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error in verify_seller: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@product.route('/debug/create-week-data')
@login_required
def create_week_test_data():
    if not current_user.is_seller:
        return jsonify({'error': 'Not a seller'}), 403
        
    try:
        # Get a product from the current seller
        product = Product.query.filter_by(seller_id=current_user.id).first()
        if not product:
            return jsonify({'error': 'No products found for seller'}), 404
        
        orders_created = []
        today = datetime.now()
        
        # Create orders for the past 7 days
        for i in range(7):
            order_date = today - timedelta(days=i)
            # Random order amount between 100 and 1000
            order_amount = float(random.randint(100, 1000))
            
            order = Order(
                user_id=current_user.id,
                status='delivered',
                total=order_amount,
                subtotal=order_amount,
                shipping=0,
                tax=0,
                shipping_address='Test Address',
                phone='1234567890',
                email=current_user.email,
                created_at=order_date
            )
            db.session.add(order)
            db.session.flush()
            
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=1,
                price=order_amount
            )
            db.session.add(order_item)
            
            orders_created.append({
                'date': order_date.strftime('%Y-%m-%d'),
                'amount': order_amount
            })
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Test orders created for the past 7 days',
            'orders': orders_created
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating test orders: {str(e)}")
        return jsonify({'error': str(e)}), 500

@product.route('/create-test-orders')
@login_required
def create_test_orders():
    if not current_user.is_seller:
        abort(403)
    
    try:
        # Get a product from the current seller
        product = Product.query.filter_by(seller_id=current_user.id).first()
        if not product:
            flash('No products found for seller', 'error')
            return redirect(url_for('product.seller_dashboard'))
        
        today = datetime.now()
        
        # Create orders for the past 7 days
        for i in range(7):
            order_date = today - timedelta(days=i)
            # Random order amount between 100 and 1000
            order_amount = random.randint(100, 1000)
            
            order = Order(
                user_id=current_user.id,
                status='delivered',
                total=order_amount,
                subtotal=order_amount,
                shipping=0,
                tax=0,
                shipping_address='Test Address',
                phone='1234567890',
                email=current_user.email,
                created_at=order_date
            )
            db.session.add(order)
            db.session.flush()
            
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=1,
                price=order_amount
            )
            db.session.add(order_item)
        
        db.session.commit()
        flash('Test orders created successfully!', 'success')
        return redirect(url_for('product.seller_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating test orders: {str(e)}', 'error')
        return redirect(url_for('product.seller_dashboard'))
