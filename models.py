from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import pytz

db = SQLAlchemy()

def current_time_ist():
    """Return current time in IST timezone."""
    return datetime.now(pytz.timezone('Asia/Kolkata'))


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, waiter, billing
    created_at = db.Column(db.DateTime, default=current_time_ist)


class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    available = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=current_time_ist)


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(15), unique=True, nullable=False)
    total_visits = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Float, default=0.0)
    last_visit = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=current_time_ist)


# ============================================================
# UPDATED COUPON MODEL - WITH ADVANCED TYPES
# ============================================================
class Coupon(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)

    # ====== COUPON TYPE ======
    # Types: 'percent', 'flat', 'bogo', 'frequency'
    discount_type = db.Column(db.String(20), nullable=False)

    # For 'percent' and 'flat' discounts
    value = db.Column(db.Float, default=0)

    # For 'bogo' type (Buy X Get Y)
    bogo_buy_quantity = db.Column(db.Integer)  # Buy this many
    bogo_get_quantity = db.Column(db.Integer)  # Get this many free
    bogo_item_ids = db.Column(db.Text)  # JSON list of applicable item IDs

    # For 'frequency' type (Every Nth purchase)
    frequency_nth_order = db.Column(db.Integer)  # Apply on every Nth order
    frequency_discount_percent = db.Column(db.Float)  # Discount %

    # ====== COMMON FIELDS ======
    min_amount = db.Column(db.Float, default=0)
    max_discount = db.Column(db.Float)  # Cap for percent discounts

    # Usage limits
    max_uses = db.Column(db.Integer)  # Total uses allowed
    current_uses = db.Column(db.Integer, default=0)

    # Validity
    is_active = db.Column(db.Boolean, default=True)
    valid_from = db.Column(db.DateTime)
    valid_until = db.Column(db.DateTime)

    # Time restrictions
    valid_days = db.Column(db.String(50))  # "0,1,2" (Mon,Tue,Wed)
    valid_hours = db.Column(db.String(50))  # "18:00-22:00"

    # Customer restrictions
    first_order_only = db.Column(db.Boolean, default=False)
    returning_customer_only = db.Column(db.Boolean, default=False)

    # Category restrictions
    applicable_categories = db.Column(db.Text)  # JSON list

    created_at = db.Column(db.DateTime, default=current_time_ist)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True)
    order_number = db.Column(db.Integer, unique=True, nullable=False)
    table_no = db.Column(db.String(10), nullable=False)
    items = db.Column(db.Text)  # JSON
    status = db.Column(db.String(20), default='pending')
    coupon_code = db.Column(db.String(50))
    discount_amount = db.Column(db.Float, default=0.0)
    customer_mobile = db.Column(db.String(15))
    created_at = db.Column(db.DateTime, default=current_time_ist)


class Table(db.Model):
    __tablename__ = 'tables'
    id = db.Column(db.Integer, primary_key=True)
    table_no = db.Column(db.String(10), unique=True, nullable=False)
    status = db.Column(db.String(20), default='available')
    locked = db.Column(db.Boolean, default=False)
    is_delivery = db.Column(db.Boolean, default=False)
    current_order_id = db.Column(db.Integer)


class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    table_no = db.Column(db.String(10))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    subtotal = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False)
    coupon_code = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=current_time_ist)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))


class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    role = db.Column(db.String(20))
    action = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=current_time_ist)


class PrintJob(db.Model):
    __tablename__ = 'print_jobs'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    content = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=current_time_ist)