import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask import current_app
import jwt
from time import time
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Define Follow model first
class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Define ChatMessage model second
class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')

# Define User model last since it depends on Follow and ChatMessage
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    is_seller = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # User profile fields
    profile_image = db.Column(db.String(200))
    phone = db.Column(db.String(15))
    address = db.Column(db.String(200))
    
    # Seller specific fields
    store_name = db.Column(db.String(100), unique=True)
    store_description = db.Column(db.Text)
    business_address = db.Column(db.String(200))
    business_type = db.Column(db.String(50))
    business_email = db.Column(db.String(120), unique=True)
    tax_id = db.Column(db.String(50))
    is_verified = db.Column(db.Boolean, default=False)
    verification_submitted_at = db.Column(db.DateTime)
    verification_approved_at = db.Column(db.DateTime)
    total_sales = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    account_status = db.Column(db.String(20), default='active')  # active, suspended, pending
    
    # Relationships
    products = db.relationship('Product', backref='seller', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref=db.backref('user', lazy=True), lazy=True)
    reviews = db.relationship('Review', backref=db.backref('user', lazy=True), lazy=True)
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
        
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active_seller(self):
        return self.is_seller and self.account_status == 'active'

    @property
    def needs_verification(self):
        return self.is_seller and not self.is_verified and not self.verification_submitted_at
        
    def __repr__(self):
        return f'<User {self.username}>'

class OAuth(OAuthConsumerMixin, db.Model):
    __tablename__ = 'flask_dance_oauth'
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    token = db.Column(db.JSON, nullable=False)
    provider_user_id = db.Column(db.String(256), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(User)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define the relationship without backref
    products = db.relationship('Product', back_populates='category', lazy=True)

class Product(db.Model):
    __tablename__ = 'product'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image_main = db.Column(db.String(200))
    image_1 = db.Column(db.String(200))
    image_2 = db.Column(db.String(200))
    image_3 = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_featured = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    featured_image = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    sold_count = db.Column(db.Integer, default=0)
    
    # Define the relationships
    category = db.relationship('Category', back_populates='products', lazy=True)
    reviews = db.relationship('Review', back_populates='product', lazy='dynamic', cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', back_populates='product', lazy='dynamic', cascade='all, delete-orphan')
    product_images = db.relationship('ProductImage', back_populates='product', lazy='dynamic', cascade='all, delete-orphan')
    flash_sales = db.relationship('FlashSale', back_populates='product', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    order_items = db.relationship('OrderItem', back_populates='product', lazy='dynamic', passive_deletes=True)
    sizes = db.relationship('ProductSize', back_populates='product', cascade='all, delete-orphan')
    
    rating = db.Column(db.Float, default=0.0)  # Average rating
    review_count = db.Column(db.Integer, default=0)

    @property
    def avg_rating(self):
        return self.rating if self.rating else 0

    @property
    def total_reviews(self):
        return self.review_count if self.review_count else 0

    def __repr__(self):
        return f'<Product {self.name}>'

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    size = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('cart_items', lazy='joined'))
    product = db.relationship('Product', back_populates='cart_items')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    total = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    shipping = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tracking_number = db.Column(db.String(100))
    courier = db.Column(db.String(100))
    estimated_delivery = db.Column(db.DateTime)
    shipping_status = db.Column(db.String(50), default='pending')
    
    # Relationships
    items = db.relationship('OrderItem', back_populates='order', lazy='joined', cascade='all, delete-orphan')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='SET NULL'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)  # Store price at time of purchase
    size = db.Column(db.String(10), nullable=False)  # Add size field
    
    product = db.relationship('Product', back_populates='order_items')
    order = db.relationship('Order', back_populates='items')



class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    media = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified_purchase = db.Column(db.Boolean, default=True)
    
    seller_response = db.Column(db.Text)
    response_date = db.Column(db.DateTime)
    
    # Relationships
    product = db.relationship('Product', back_populates='reviews')
    order = db.relationship('Order', backref='reviews')
    images = db.relationship('ReviewImage', back_populates='review', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Review {self.id} by {self.user.username}>'
        
    def update_seller_rating(self):
        """Update the seller's rating and review count when a review is submitted"""
        seller = self.product.seller
        # Get all reviews for all products by this seller
        seller_reviews = Review.query.join(Product).filter(Product.seller_id == seller.id).all()
        
        if seller_reviews:
            # Calculate average rating
            total_rating = sum(review.rating for review in seller_reviews)
            seller.rating = total_rating / len(seller_reviews)
            seller.review_count = len(seller_reviews)
            db.session.add(seller)
            db.session.commit()
            print(f"Updated seller rating to {seller.rating} with {seller.review_count} reviews")

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', back_populates='product_images')

class FlashSale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    discount_percentage = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    sold = db.Column(db.Integer, default=0)
    
    product = db.relationship('Product', back_populates='flash_sales')

class ShipmentTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    tracking_number = db.Column(db.String(100))
    courier = db.Column(db.String(100))
    
    order = db.relationship('Order', backref='tracking_updates')

class ReviewImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    review = db.relationship('Review', back_populates='images')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    reference_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref='notifications')

class ProductSize(db.Model):
    __tablename__ = 'product_sizes'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    size = db.Column(db.String(10), nullable=False)
    stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    product = db.relationship('Product', back_populates='sizes')

    def __repr__(self):
        return f'<ProductSize {self.size} for Product {self.product_id}>'

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    # Updated relationships with unique backref names
    sender = db.relationship('User', foreign_keys=[sender_id], backref=db.backref('messages_sent', lazy=True))
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref=db.backref('messages_received', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'is_read': self.is_read,
            'sender_name': self.sender.username,
            'sender_image': self.sender.profile_image
        }
