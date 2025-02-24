"""initial migration

Revision ID: 066179586d5f
Revises: 
Create Date: 2024-12-06 23:18:43.630448

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '066179586d5f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('idx_orderitem_product', table_name='order_item')
    op.drop_table('order_item')
    op.drop_index('idx_order_created_at', table_name='order')
    op.drop_index('idx_order_status', table_name='order')
    op.drop_table('order')
    op.drop_index('idx_order_tracking', table_name='shipment_tracking')
    op.drop_table('shipment_tracking')
    op.drop_table('cart_item')
    op.drop_index('slug', table_name='category')
    op.drop_table('category')
    op.drop_index('email', table_name='user')
    op.drop_index('idx_user_email', table_name='user')
    op.drop_index('idx_user_username', table_name='user')
    op.drop_index('reset_token', table_name='user')
    op.drop_index('unique_email', table_name='user')
    op.drop_index('username', table_name='user')
    op.drop_index('username_2', table_name='user')
    op.drop_table('user')
    op.drop_table('flash_sale')
    op.drop_table('chat_messages')
    op.drop_table('review_image')
    op.drop_index('idx_oauth_user_id', table_name='oauth')
    op.drop_index('unique_provider_user', table_name='oauth')
    op.drop_table('oauth')
    op.drop_index('idx_review_order', table_name='review')
    op.drop_index('idx_review_product', table_name='review')
    op.drop_index('idx_review_user', table_name='review')
    op.drop_table('review')
    op.drop_table('product_image')
    op.drop_index('idx_product_rating', table_name='product')
    op.drop_index('idx_product_seller', table_name='product')
    op.drop_index('slug', table_name='product')
    op.drop_table('product')
    op.drop_table('follows')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('follows',
    sa.Column('follower_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('followed_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('created_at', mysql.DATETIME(), server_default=sa.text('current_timestamp()'), nullable=True),
    sa.ForeignKeyConstraint(['followed_id'], ['user.id'], name='follows_ibfk_2'),
    sa.ForeignKeyConstraint(['follower_id'], ['user.id'], name='follows_ibfk_1'),
    sa.PrimaryKeyConstraint('follower_id', 'followed_id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_table('product',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('name', mysql.VARCHAR(length=200), nullable=False),
    sa.Column('slug', mysql.VARCHAR(length=200), nullable=False),
    sa.Column('description', mysql.TEXT(), nullable=True),
    sa.Column('price', mysql.FLOAT(), nullable=False),
    sa.Column('stock', mysql.INTEGER(display_width=11), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('image_main', mysql.VARCHAR(length=200), nullable=True),
    sa.Column('image_1', mysql.VARCHAR(length=200), nullable=True),
    sa.Column('image_2', mysql.VARCHAR(length=200), nullable=True),
    sa.Column('image_3', mysql.VARCHAR(length=200), nullable=True),
    sa.Column('category_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('seller_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('created_at', mysql.DATETIME(), server_default=sa.text('current_timestamp()'), nullable=True),
    sa.Column('updated_at', mysql.DATETIME(), server_default=sa.text('current_timestamp() ON UPDATE current_timestamp()'), nullable=True),
    sa.Column('is_featured', mysql.TINYINT(display_width=1), server_default=sa.text('0'), autoincrement=False, nullable=False),
    sa.Column('is_archived', mysql.TINYINT(display_width=1), server_default=sa.text('0'), autoincrement=False, nullable=False),
    sa.Column('featured_image', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('is_active', mysql.TINYINT(display_width=1), server_default=sa.text('1'), autoincrement=False, nullable=True),
    sa.Column('rating', mysql.FLOAT(), server_default=sa.text('0'), nullable=True),
    sa.Column('review_count', mysql.INTEGER(display_width=11), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('sold_count', mysql.INTEGER(display_width=11), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('in_wishlist_count', mysql.INTEGER(display_width=11), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], name='product_category_fk', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('slug', 'product', ['slug'], unique=True)
    op.create_index('idx_product_seller', 'product', ['seller_id'], unique=False)
    op.create_index('idx_product_rating', 'product', ['rating'], unique=False)
    op.create_table('product_image',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('product_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('image_path', mysql.VARCHAR(length=255), nullable=False),
    sa.Column('created_at', mysql.TIMESTAMP(), server_default=sa.text('current_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='product_image_ibfk_1', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_table('review',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('user_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('product_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('rating', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('comment', mysql.TEXT(), nullable=False),
    sa.Column('created_at', mysql.DATETIME(), server_default=sa.text('current_timestamp()'), nullable=True),
    sa.Column('seller_response', mysql.TEXT(), nullable=True),
    sa.Column('response_date', mysql.DATETIME(), nullable=True),
    sa.Column('media', mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'), nullable=True),
    sa.Column('is_verified_purchase', mysql.TINYINT(display_width=1), server_default=sa.text('1'), autoincrement=False, nullable=True),
    sa.Column('variation', mysql.VARCHAR(length=100), nullable=True),
    sa.Column('order_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['order_id'], ['order.id'], name='fk_review_order'),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='review_ibfk_2', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='review_ibfk_1'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('idx_review_user', 'review', ['user_id'], unique=False)
    op.create_index('idx_review_product', 'review', ['product_id'], unique=False)
    op.create_index('idx_review_order', 'review', ['order_id'], unique=False)
    op.create_table('oauth',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('provider', mysql.VARCHAR(length=255), nullable=False),
    sa.Column('created_at', mysql.TIMESTAMP(), server_default=sa.text('current_timestamp()'), nullable=False),
    sa.Column('token', mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'), nullable=True),
    sa.Column('provider_user_id', mysql.VARCHAR(length=256), nullable=False),
    sa.Column('provider_user_login', mysql.VARCHAR(length=256), nullable=True),
    sa.Column('user_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='oauth_ibfk_1'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('unique_provider_user', 'oauth', ['provider', 'provider_user_id'], unique=True)
    op.create_index('idx_oauth_user_id', 'oauth', ['user_id'], unique=False)
    op.create_table('review_image',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('review_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('image_path', mysql.VARCHAR(length=255), nullable=False),
    sa.Column('created_at', mysql.TIMESTAMP(), server_default=sa.text('current_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['review_id'], ['review.id'], name='review_image_ibfk_1', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_table('chat_messages',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('sender_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('recipient_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('content', mysql.TEXT(), nullable=False),
    sa.Column('timestamp', mysql.DATETIME(), server_default=sa.text('current_timestamp()'), nullable=True),
    sa.Column('is_read', mysql.TINYINT(display_width=1), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['recipient_id'], ['user.id'], name='chat_messages_ibfk_2'),
    sa.ForeignKeyConstraint(['sender_id'], ['user.id'], name='chat_messages_ibfk_1'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_table('flash_sale',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('product_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('discount_percentage', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('start_time', mysql.DATETIME(), nullable=False),
    sa.Column('end_time', mysql.DATETIME(), nullable=False),
    sa.Column('quantity', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('sold', mysql.INTEGER(display_width=11), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='flash_sale_ibfk_1', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_unicode_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_table('user',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('email', mysql.VARCHAR(length=100), nullable=False),
    sa.Column('password', mysql.VARCHAR(length=100), nullable=False),
    sa.Column('username', mysql.VARCHAR(length=100), nullable=False),
    sa.Column('created_at', mysql.DATETIME(), server_default=sa.text('current_timestamp()'), nullable=True),
    sa.Column('updated_at', mysql.DATETIME(), server_default=sa.text('current_timestamp() ON UPDATE current_timestamp()'), nullable=True),
    sa.Column('is_seller', mysql.TINYINT(display_width=1), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('store_name', mysql.VARCHAR(length=100), nullable=True),
    sa.Column('store_description', mysql.TEXT(), nullable=True),
    sa.Column('store_logo', mysql.VARCHAR(length=200), nullable=True),
    sa.Column('reset_token', mysql.VARCHAR(length=100), nullable=True),
    sa.Column('reset_token_expiry', mysql.DATETIME(), nullable=True),
    sa.Column('profile_image', mysql.VARCHAR(length=200), nullable=True),
    sa.Column('phone', mysql.VARCHAR(length=20), nullable=True),
    sa.Column('address', mysql.TEXT(), nullable=True),
    sa.Column('store_image', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('wishlist_count', mysql.INTEGER(display_width=11), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('image', mysql.VARCHAR(length=120), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('username_2', 'user', ['username'], unique=True)
    op.create_index('username', 'user', ['username'], unique=True)
    op.create_index('unique_email', 'user', ['email'], unique=True)
    op.create_index('reset_token', 'user', ['reset_token'], unique=True)
    op.create_index('idx_user_username', 'user', ['username'], unique=False)
    op.create_index('idx_user_email', 'user', ['email'], unique=False)
    op.create_index('email', 'user', ['email'], unique=True)
    op.create_table('category',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('NAME', mysql.VARCHAR(length=100), nullable=False),
    sa.Column('description', mysql.TEXT(), nullable=True),
    sa.Column('slug', mysql.VARCHAR(length=100), nullable=False),
    sa.Column('created_at', mysql.TIMESTAMP(), server_default=sa.text('current_timestamp()'), nullable=False),
    sa.Column('updated_at', mysql.TIMESTAMP(), server_default=sa.text('current_timestamp() ON UPDATE current_timestamp()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('slug', 'category', ['slug'], unique=True)
    op.create_table('cart_item',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('user_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('product_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('quantity', mysql.INTEGER(display_width=11), server_default=sa.text('1'), autoincrement=False, nullable=False),
    sa.Column('created_at', mysql.DATETIME(), server_default=sa.text('current_timestamp()'), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='cart_item_ibfk_2', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='cart_item_ibfk_1'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_table('shipment_tracking',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('order_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('status', mysql.VARCHAR(length=50), nullable=False),
    sa.Column('location', mysql.VARCHAR(length=200), nullable=True),
    sa.Column('description', mysql.TEXT(), nullable=True),
    sa.Column('timestamp', mysql.DATETIME(), server_default=sa.text('current_timestamp()'), nullable=True),
    sa.Column('tracking_number', mysql.VARCHAR(length=100), nullable=True),
    sa.Column('courier', mysql.VARCHAR(length=100), nullable=True),
    sa.ForeignKeyConstraint(['order_id'], ['order.id'], name='shipment_tracking_ibfk_1', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('idx_order_tracking', 'shipment_tracking', ['order_id'], unique=False)
    op.create_table('order',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('user_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('status', mysql.VARCHAR(length=20), server_default=sa.text("'processing'"), nullable=True),
    sa.Column('total', mysql.FLOAT(), nullable=False),
    sa.Column('shipping_address', mysql.TEXT(), nullable=False),
    sa.Column('created_at', mysql.DATETIME(), server_default=sa.text('current_timestamp()'), nullable=True),
    sa.Column('subtotal', mysql.FLOAT(), server_default=sa.text('0'), nullable=False),
    sa.Column('shipping', mysql.FLOAT(), server_default=sa.text('0'), nullable=False),
    sa.Column('tax', mysql.FLOAT(), server_default=sa.text('0'), nullable=False),
    sa.Column('phone', mysql.VARCHAR(length=20), server_default=sa.text("''"), nullable=False),
    sa.Column('email', mysql.VARCHAR(length=100), server_default=sa.text("''"), nullable=False),
    sa.Column('tracking_number', mysql.VARCHAR(length=100), nullable=True),
    sa.Column('courier', mysql.VARCHAR(length=100), nullable=True),
    sa.Column('estimated_delivery', mysql.DATETIME(), nullable=True),
    sa.Column('shipping_status', mysql.VARCHAR(length=50), server_default=sa.text("'pending'"), nullable=True),
    sa.Column('updated_at', mysql.DATETIME(), server_default=sa.text('current_timestamp() ON UPDATE current_timestamp()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='order_ibfk_1', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('idx_order_status', 'order', ['status'], unique=False)
    op.create_index('idx_order_created_at', 'order', ['created_at'], unique=False)
    op.create_table('order_item',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('order_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('product_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('quantity', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('price', mysql.FLOAT(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['order.id'], name='order_item_ibfk_1', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='order_item_ibfk_2', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('idx_orderitem_product', 'order_item', ['product_id'], unique=False)
    # ### end Alembic commands ###
