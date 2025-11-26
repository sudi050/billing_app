from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from printer_agent import create_kot_print_job, create_bill_print_job, format_bill_content
from datetime import datetime
import uuid, json, os
from io import StringIO, BytesIO
from models import db, User, MenuItem, Customer, Coupon, Order, Table, Bill, Log, PrintJob, current_time_ist
from werkzeug.security import check_password_hash
from sqlalchemy import extract
import calendar
import csv
from flask import make_response
from urllib.parse import quote_plus

# ============================================================
# CONFIGURATION - Set deployment mode
# ============================================================
# Set to True for cloud dashboard (read-only admin)
# Set to False for full restaurant operations (default)
CLOUD_MODE = os.environ.get('CLOUD_MODE', 'False').lower() == 'true'

# Printer configuration (only for local mode)
PRINTER_ENABLED = not CLOUD_MODE
BLUETOOTH_PRINTER_MAC = os.environ.get('PRINTER_MAC', '00:11:22:33:44:55')  # HOP-HL58 MAC address

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret')

# Database path - different for cloud and local
if CLOUD_MODE:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/shawarmaspot/database.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

PRINTER_ENABLED = True
BLUETOOTH_PRINTER_MAC = "00:11:22:33:44:55"  # Your HOP-HL58 MAC

@app.route('/print_kot/<int:table_id>', methods=['POST'])
@login_required
def print_kot(table_id):
    """Print Kitchen Order Ticket for a table"""
    print(f"DEBUG: print_kot called for table_id={table_id}")
    
    # Find table and its active order
    table = Table.query.get(table_id)
    if not table or not table.current_order_id:
        print(f"DEBUG: No order found for table {table_id}")
        return jsonify(success=False, message='No active order for this table')
    
    order = Order.query.get(table.current_order_id)
    if not order:
        print(f"DEBUG: Order not found")
        return jsonify(success=False, message='Order not found')
    
    print(f"DEBUG: Found order #{order.order_number}")
    
    try:
        items = json.loads(order.items)
        print(f"DEBUG: Loaded {len(items)} items")
    except Exception as e:
        print(f"DEBUG: Error loading items: {e}")
        return jsonify(success=False, message='Error loading order items')
    
    if not items:
        return jsonify(success=False, message='No items in order')
    
    # Kitchen 1 categories (whitelist) - UPDATE THIS LIST
    kitchen_1_cats = ['Shawarma']
    
    # Split items: Kitchen 1 = whitelist, Kitchen 2 = everything else
    kitchen_1_items = []
    kitchen_2_items = []
    
    for item in items:
        # Add category if missing
        if 'category' not in item:
            menu_item = MenuItem.query.get(item['id'])
            if menu_item:
                item['category'] = menu_item.category
        
        # Check which kitchen
        item_category = item.get('category', 'Uncategorized')
        
        if item_category in kitchen_1_cats:
            kitchen_1_items.append(item)
        else:
            kitchen_2_items.append(item)
    
    print(f"DEBUG: Kitchen 1 (Beverages) items: {len(kitchen_1_items)}")
    print(f"DEBUG: Kitchen 2 (Food) items: {len(kitchen_2_items)}")
    
    from printer_agent import format_kot_content
    
    messages = []
    all_kot_content = []
    
    # Kitchen 1
    if kitchen_1_items:
        content_1 = format_kot_content(order, kitchen_1_items)
        all_kot_content.append(f"\n=== KITCHEN 1 ===\n{content_1}")
        messages.append('Kitchen 1: Ready')
    
    # Kitchen 2
    if kitchen_2_items:
        content_2 = format_kot_content(order, kitchen_2_items)
        all_kot_content.append(f"\n=== KITCHEN 2 ===\n{content_2}")
        messages.append('Kitchen 2: Ready')
    
    # Combine all KOTs
    combined_kot = "\n".join(all_kot_content)
    
    # Log the action
    db.session.add(Log(
        username=current_user.username,
        role=current_user.role,
        action=f"Printed KOT for Order #{order.order_number}, Table {table.table_no}"
    ))
    db.session.commit()
    
    return jsonify(
        success=True, 
        message=' | '.join(messages),
        kot_content=combined_kot  # Send content to JavaScript
    )


# ============================================================
# PRINTER FUNCTIONS (Local Mode Only)
# ============================================================
if PRINTER_ENABLED:
    try:
        from escpos.printer import Bluetooth

        def print_to_thermal(content):
            """Print content to Bluetooth thermal printer."""
            try:
                printer = Bluetooth(BLUETOOTH_PRINTER_MAC)
                printer.text(content)
                printer.cut()
                return True, "Printed successfully"
            except Exception as e:
                return False, f"Print error: {str(e)}"

    except ImportError:
        print("⚠️ python-escpos not installed. Bluetooth printing disabled.")
        PRINTER_ENABLED = False

        def print_to_thermal(content):
            return False, "Printer library not installed"


# ============================================================
# DECORATOR: Disable route in cloud mode
# ============================================================
def local_only(f):
    """Decorator to disable routes in cloud mode."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if CLOUD_MODE:
            flash("This feature is only available on the local restaurant server.", "warning")
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# TEMPLATE FILTER
# ============================================================
@app.template_filter('from_json')
def from_json_filter(s):
    try:
        return json.loads(s) if s else []
    except:
        return []
    
# -------------------- Routes --------------------
# -------------------- HELPER FUNCTIONS --------------------
def validate_coupon(coupon, order, customer=None):
    """
    Validates if a coupon can be applied to an order.
    Supports: percent, flat, bogo, frequency types
    Returns (is_valid, error_message)
    """
    # Rule 1: Check if coupon is active
    if not coupon.is_active:
        return False, "This coupon is not active."

    # Rule 2: Check usage limit
    if coupon.max_uses and coupon.current_uses >= coupon.max_uses:
        return False, "This coupon has reached its usage limit."

    # Rule 3: Check date/time validity
    now = current_time_ist()
    if coupon.valid_from and now < coupon.valid_from:
        return False, "This coupon is not yet valid."
    if coupon.valid_until and now > coupon.valid_until:
        return False, "This coupon has expired."

    # Rule 4: Check day of week
    if coupon.valid_days:
        valid_days = [int(d) for d in coupon.valid_days.split(',')]
        if now.weekday() not in valid_days:
            days_map = {0:'Mon', 1:'Tue', 2:'Wed', 3:'Thu', 4:'Fri', 5:'Sat', 6:'Sun'}
            valid_names = [days_map[d] for d in valid_days]
            return False, f"This coupon is only valid on: {', '.join(valid_names)}"

    # Rule 5: Check time of day
    if coupon.valid_hours:
        start_time, end_time = coupon.valid_hours.split('-')
        current_time = now.strftime("%H:%M")
        if not (start_time <= current_time <= end_time):
            return False, f"This coupon is only valid between {start_time} and {end_time}"

    # Rule 6: Check minimum amount
    items = json.loads(order.items) if order.items else []
    subtotal = sum(item['qty'] * item['price'] for item in items)
    if subtotal < coupon.min_amount:
        return False, f"Minimum order of ₹{coupon.min_amount} required."

    # Rule 7: Check category restrictions
    if coupon.applicable_categories:
        try:
            applicable = json.loads(coupon.applicable_categories)
            item_categories = [MenuItem.query.get(i['id']).category for i in items if MenuItem.query.get(i['id'])]
            if not any(cat in applicable for cat in item_categories):
                return False, "This coupon doesn't apply to items in your cart."
        except:
            pass

    # Rule 8: Check customer type (first-time vs returning)
    if customer:
        if coupon.first_order_only and customer.total_visits > 0:
            return False, "This coupon is for first-time customers only."
        if coupon.returning_customer_only and customer.total_visits == 0:
            return False, "This coupon is for returning customers only."

    # ============================================================
    # NEW: FREQUENCY-BASED COUPON VALIDATION
    # ============================================================
    if coupon.discount_type == 'frequency':
        if not customer:
            return False, "Phone number required for frequency-based discounts."

        # Check if this is the Nth order
        nth = coupon.frequency_nth_order or 5
        if (customer.total_visits + 1) % nth != 0:
            remaining = nth - ((customer.total_visits + 1) % nth)
            return False, f"This discount applies on every {nth}th order. {remaining} more orders to go!"

    # ============================================================
    # NEW: BOGO COUPON VALIDATION
    # ============================================================
    if coupon.discount_type == 'bogo':
        if not coupon.bogo_item_ids:
            return False, "Invalid BOGO configuration."

        # Check if cart contains applicable items
        try:
            applicable_item_ids = json.loads(coupon.bogo_item_ids)
            cart_item_ids = [item['id'] for item in items]

            if not any(item_id in applicable_item_ids for item_id in cart_item_ids):
                applicable_items = [MenuItem.query.get(item_id).name for item_id in applicable_item_ids if MenuItem.query.get(item_id)]
                return False, f"This offer applies only to: {', '.join(applicable_items)}"

            # Check minimum quantity for BOGO
            buy_qty = coupon.bogo_buy_quantity or 1
            total_applicable = sum(item['qty'] for item in items if item['id'] in applicable_item_ids)

            if total_applicable < buy_qty:
                return False, f"Buy at least {buy_qty} items to avail this offer."

        except Exception as e:
            return False, "Error validating BOGO offer."

    return True, None


def calculate_discount(coupon, subtotal, items=None, customer=None):
    """
    Calculate discount amount based on coupon type.
    Supports: percent, flat, bogo, frequency
    """
    discount_amount = 0.0

    # ============================================================
    # PERCENT DISCOUNT
    # ============================================================
    if coupon.discount_type == "percent":
        if coupon.value < 0 or coupon.value > 100:
            return 0.0
        discount_amount = subtotal * (coupon.value / 100)

        # Apply max discount cap
        if coupon.max_discount:
            discount_amount = min(discount_amount, coupon.max_discount)

    # ============================================================
    # FLAT DISCOUNT
    # ============================================================
    elif coupon.discount_type == "flat":
        discount_amount = min(coupon.value, subtotal)

    # ============================================================
    # NEW: FREQUENCY-BASED DISCOUNT
    # ============================================================
    elif coupon.discount_type == "frequency":
        if not customer:
            return 0.0

        # Check if this is the Nth order
        nth = coupon.frequency_nth_order or 5
        if (customer.total_visits + 1) % nth == 0:
            discount_percent = coupon.frequency_discount_percent or 20
            discount_amount = subtotal * (discount_percent / 100)

            # Apply max discount cap
            if coupon.max_discount:
                discount_amount = min(discount_amount, coupon.max_discount)

    # ============================================================
    # NEW: BOGO (Buy X Get Y)
    # ============================================================
    elif coupon.discount_type == "bogo":
        if not items or not coupon.bogo_item_ids:
            return 0.0

        try:
            applicable_item_ids = json.loads(coupon.bogo_item_ids)
            buy_qty = coupon.bogo_buy_quantity or 1
            get_qty = coupon.bogo_get_quantity or 1

            # Find applicable items in cart
            applicable_items = [item for item in items if item['id'] in applicable_item_ids]

            if not applicable_items:
                return 0.0

            # Calculate BOGO discount
            # For each set of (buy_qty + get_qty), discount the price of get_qty items
            for item in applicable_items:
                total_qty = item['qty']
                sets = total_qty // (buy_qty + get_qty)

                if sets > 0:
                    # Discount = price of free items
                    free_items = sets * get_qty
                    discount_amount += free_items * item['price']

            # Alternative: If any applicable items exist, give cheapest items free
            # This is more common for "Buy 1 Get 1 Free" type offers
            if discount_amount == 0 and applicable_items:
                # Sort by price
                sorted_items = sorted(applicable_items, key=lambda x: x['price'])
                total_qty = sum(item['qty'] for item in applicable_items)

                sets = total_qty // (buy_qty + get_qty)
                if sets > 0:
                    # Give cheapest items free
                    free_items_count = sets * get_qty
                    items_to_discount = []

                    for item in sorted_items:
                        if len(items_to_discount) >= free_items_count:
                            break
                        for _ in range(min(item['qty'], free_items_count - len(items_to_discount))):
                            items_to_discount.append(item['price'])

                    discount_amount = sum(items_to_discount)

        except Exception as e:
            print(f"BOGO calculation error: {e}")
            return 0.0

    return round(discount_amount, 2)


# ============================================================
# HELPER: Get discount description for display
# ============================================================
def get_discount_description(coupon, customer=None):
    """Return human-readable description of discount."""
    if coupon.discount_type == 'percent':
        return f"{coupon.value}% off (max ₹{coupon.max_discount or 'unlimited'})"

    elif coupon.discount_type == 'flat':
        return f"₹{coupon.value} off"

    elif coupon.discount_type == 'frequency':
        nth = coupon.frequency_nth_order or 5
        discount = coupon.frequency_discount_percent or 20
        if customer:
            next_eligible = nth - ((customer.total_visits + 1) % nth)
            if next_eligible == nth:
                return f"🎉 {discount}% off on this order! (Every {nth}th order)"
            else:
                return f"{discount}% off every {nth}th order ({next_eligible} more to go)"
        return f"{discount}% off on every {nth}th order"

    elif coupon.discount_type == 'bogo':
        buy = coupon.bogo_buy_quantity or 1
        get = coupon.bogo_get_quantity or 1
        return f"Buy {buy} Get {get} Free"

    return "Special Discount"

# -------------------- USER LOADER --------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------- AUTHENTICATION --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            try:
                db.session.add(Log(username=username, role=user.role, action='login'))
                db.session.commit()
            except:
                db.session.rollback()

            if user.role == 'waiter':
                return redirect(url_for('waiter'))
            elif user.role == 'billing':
                return redirect(url_for('billing'))
            else:
                return redirect(url_for('admin_menu'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    try:
        db.session.add(Log(username=current_user.username, role=current_user.role, action='logout'))
        db.session.commit()
    except:
        db.session.rollback()
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    if current_user.role == 'waiter':
        return redirect(url_for('waiter'))
    elif current_user.role == 'billing':
        return redirect(url_for('billing'))
    else:
        return redirect(url_for('admin_menu'))


# -------------------- ADMIN DASHBOARD --------------------
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    """Admin dashboard with complete statistics."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    from sqlalchemy import func
    from datetime import datetime, timedelta

    # REVENUE STATISTICS
    total_revenue = db.session.query(func.sum(Bill.total)).scalar() or 0.0
    total_discount = db.session.query(func.sum(Bill.discount)).scalar() or 0.0
    total_bills_count = Bill.query.count()
    avg_bill = (total_revenue / total_bills_count) if total_bills_count > 0 else 0.0

    # Today's stats
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    today_revenue = db.session.query(func.sum(Bill.total))\
        .filter(Bill.created_at.between(today_start, today_end)).scalar() or 0.0
    today_discount = db.session.query(func.sum(Bill.discount))\
        .filter(Bill.created_at.between(today_start, today_end)).scalar() or 0.0
    today_bills_count = Bill.query.filter(Bill.created_at.between(today_start, today_end)).count()
    today_avg_bill = (today_revenue / today_bills_count) if today_bills_count > 0 else 0.0

    # ORDER STATISTICS
    total_orders = Order.query.count()
    today_orders = Order.query.filter(Order.created_at.between(today_start, today_end)).count()
    pending_orders = Order.query.filter_by(status='pending').count()
    served_orders = Order.query.filter_by(status='served').count()
    billed_orders = Order.query.filter_by(status='billed').count()

    # CUSTOMER STATISTICS
    total_customers = Customer.query.count()
    today_customers = Customer.query.filter(Customer.created_at.between(today_start, today_end)).count()
    top_customers = Customer.query.order_by(Customer.total_spent.desc()).limit(5).all()
    avg_customer_spend = db.session.query(func.avg(Customer.total_spent)).scalar() or 0.0

    # TABLE STATISTICS
    total_tables = Table.query.filter_by(is_delivery=False).count()
    active_tables = Table.query.filter_by(locked=True, is_delivery=False).count()
    available_tables = Table.query.filter_by(locked=False, is_delivery=False).count()
    occupancy_rate = (active_tables / total_tables * 100) if total_tables > 0 else 0.0

    # MENU STATISTICS
    total_menu_items = MenuItem.query.count()
    available_items = MenuItem.query.filter_by(available=True).count()
    unavailable_items = MenuItem.query.filter_by(available=False).count()

    # COUPON STATISTICS
    total_coupons = Coupon.query.count()
    active_coupons = Coupon.query.filter_by(is_active=True).count()
    total_coupon_uses = db.session.query(func.sum(Coupon.current_uses)).scalar() or 0
    discount_rate = (total_discount / (total_revenue + total_discount) * 100) if (total_revenue + total_discount) > 0 else 0.0

    # RECENT ACTIVITY
    recent_bills = Bill.query.order_by(Bill.created_at.desc()).limit(10).all()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    recent_logs = Log.query.order_by(Log.timestamp.desc()).limit(20).all()

    return render_template('admin.html',
        total_revenue=total_revenue, total_discount=total_discount, avg_bill=avg_bill,
        today_revenue=today_revenue, today_discount=today_discount, today_avg_bill=today_avg_bill,
        discount_rate=discount_rate, total_bills_count=total_bills_count, today_bills_count=today_bills_count,
        total_orders=total_orders, today_orders=today_orders, pending_orders=pending_orders,
        served_orders=served_orders, billed_orders=billed_orders,
        total_customers=total_customers, today_customers=today_customers, 
        top_customers=top_customers, avg_customer_spend=avg_customer_spend,
        total_tables=total_tables, active_tables=active_tables, available_tables=available_tables,
        occupancy_rate=occupancy_rate, total_menu_items=total_menu_items,
        available_items=available_items, unavailable_items=unavailable_items,
        total_coupons=total_coupons, active_coupons=active_coupons, total_coupon_uses=total_coupon_uses,
        recent_bills=recent_bills, recent_orders=recent_orders, recent_logs=recent_logs)





# -------------------- PRINT PREVIEW --------------------
@app.route('/print/preview')
@login_required
def print_preview():
    """Display print preview for thermal printer."""
    from urllib.parse import unquote_plus

    # Get and decode the content
    encoded_content = request.args.get("content", "")
    content = unquote_plus(encoded_content) if encoded_content else ""

    return render_template("print_preview.html", content=content)


# -------------------- WAITER SECTION --------------------
@app.route('/waiter', methods=['GET', 'POST'])
@login_required
def waiter():
    if current_user.role not in ['admin', 'waiter']:
        return redirect(url_for('index'))

    tables = Table.query.order_by(Table.table_no).all()
    selected_table_id = request.args.get('table_id', type=int)
    selected_table = None
    active_order = None
    cart = []

    if selected_table_id:
        selected_table = Table.query.get(selected_table_id)
        if selected_table and selected_table.current_order_id:
            active_order = Order.query.get(selected_table.current_order_id)
            cart = json.loads(active_order.items) if active_order and active_order.items else []

    menu_items = MenuItem.query.filter_by(available=True).order_by(MenuItem.category, MenuItem.name).all()
    menu_by_category = {}
    for item in menu_items:
        cat = item.category or "Uncategorized"
        menu_by_category.setdefault(cat, []).append(item)

    # --- Add item ---
    if request.method == 'POST' and 'add_item' in request.form:
        try:
            table_id = int(request.form['table_id'])
            item_id = int(request.form['item_id'])
            qty = int(request.form.get('qty', 1))

            # Validate quantity
            if qty <= 0 or qty > 100:
                flash("Invalid quantity. Please enter between 1-100.", "danger")
                return redirect(url_for('waiter'))

            table = Table.query.get(table_id)
            item = MenuItem.query.get(item_id)

            if not table or not item:
                flash("Invalid selection", "danger")
                return redirect(url_for('waiter'))

            if not table.current_order_id:
                last_order = Order.query.order_by(Order.order_number.desc()).first()
                next_order_number = 1001 if not last_order else last_order.order_number + 1

                order = Order(
                    uuid=str(uuid.uuid4()),
                    order_number=next_order_number,
                    table_no=table.table_no,
                    items=json.dumps([]),
                    status='pending'
                )

                db.session.add(order)
                db.session.flush()
                table.current_order_id = order.id
                table.locked = True
                table.status = 'occupied'

            order = Order.query.get(table.current_order_id)
            cart = json.loads(order.items) if order.items else []

            # Update qty or add
            item_found = False
            for c in cart:
                if c['id'] == item.id:
                    c['qty'] += qty
                    item_found = True
                    break

            if not item_found:
                cart.append({
                    'id': item.id,
                    'name': item.name,
                    'price': item.price,
                    'qty': qty,
                    'category': item.category
                })


            order.items = json.dumps(cart)
            order.coupon_code = None
            order.discount_amount = 0.0

            db.session.add(Log(
                username=current_user.username,
                role=current_user.role,
                action=f"Added {item.name} x{qty} to table {table.table_no}"
            ))
            db.session.commit()

            flash(f"Added {qty}x {item.name} to Table {table.table_no}", "success")
            return redirect(url_for('waiter', table_id=table.id))


        except ValueError:
            flash("Invalid input values", "danger")
            return redirect(url_for('waiter'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding item: {str(e)}", "danger")
            return redirect(url_for('waiter'))

    # --- Remove item ---
    if request.method == 'POST' and 'remove_item' in request.form:
        try:
            table_id = int(request.form['table_id'])
            item_id = int(request.form['remove_item'])

            table = Table.query.get(table_id)
            if not table or not table.current_order_id:
                flash("No active order found", "danger")
                return redirect(url_for('waiter'))

            order = Order.query.get(table.current_order_id)
            cart = [c for c in json.loads(order.items) if c['id'] != item_id]
            order.items = json.dumps(cart)

            order.coupon_code = None
            order.discount_amount = 0.0

            db.session.commit()
            flash("Item removed", "info")
            return redirect(url_for('waiter', table_id=table.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error removing item: {str(e)}", "danger")
            return redirect(url_for('waiter'))

    return render_template('waiter.html',
                           tables=tables,
                           selected_table=selected_table,
                           cart=cart,
                           menu_by_category=menu_by_category)


# -------------------- KITCHEN SECTION --------------------
@app.route('/kitchen')
@login_required
def kitchen():
    if current_user.role not in ['admin', 'waiter']:
        return redirect(url_for('index'))

    orders = Order.query.filter_by(status='pending').order_by(Order.created_at.asc()).all()
    return render_template('kitchen.html', orders=orders)


@app.route('/order/serve/<int:order_id>', methods=['POST'])
@login_required
def serve_order(order_id):
    try:
        o = Order.query.get(order_id)
        if not o:
            return "Not found", 404

        o.status = "served"
        db.session.add(Log(
            username=current_user.username,
            role=current_user.role,
            action=f"served_order:{o.id}"
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error serving order: {str(e)}", "danger")

    return redirect(url_for('kitchen'))


# -------------------- BILLING SECTION --------------------
@app.route('/billing', methods=['GET', 'POST'])
@login_required
def billing():
    if current_user.role not in ['admin', 'billing']:
        return redirect(url_for('index'))

    tables = Table.query.filter(Table.locked == True, Table.is_delivery == False).all()
    delivery_table = Table.query.filter_by(is_delivery=True).first()

    selected_table_no = request.args.get('table_no') or request.form.get('table_no')
    selected_order = None
    items = []
    subtotal_amount = discount_amount = total_amount = 0.0
    customer = None

    if selected_table_no:
        selected_order = (
            Order.query.join(Table, Order.table_no == Table.table_no)
            .filter(Table.table_no == selected_table_no, Order.status.in_(['pending', 'served']))
            .first()
        )

        # ========================================
        # APPLY COUPON
        # ========================================
        if request.method == "POST" and "apply_coupon" in request.form:
            try:
                print("\n" + "="*60)
                print("🎟️  APPLY COUPON REQUEST RECEIVED")
                print("="*60)
                
                # Log ALL form data received
                print(f"📋 All Form Keys: {list(request.form.keys())}")
                print(f"📋 All Form Data:")
                for key, value in request.form.items():
                    print(f"   {key}: '{value}'")
                
                # Get coupon code
                coupon_code = request.form.get("coupon_code_manual", "").strip().upper()
                customer_mobile = request.form.get("customer_mobile", "").strip()
                customer_name = request.form.get("customer_name", "").strip()

                print(f"\n📊 Extracted Data:")
                print(f"   Coupon Code: '{coupon_code}'")
                print(f"   Customer Mobile: '{customer_mobile}'")
                print(f"   Customer Name: '{customer_name}'")
                print(f"   Order #: {selected_order.order_number}")
                print(f"   Table: {selected_table_no}")

                # Validation
                if not coupon_code:
                    print("❌ ERROR: Coupon code is empty!")
                    flash("⚠️ Please enter or select a coupon code", "warning")
                    return redirect(url_for('billing', table_no=selected_table_no))

                print(f"\n🔍 Looking up coupon '{coupon_code}' in database...")
                coupon = Coupon.query.filter_by(code=coupon_code).first()

                if not coupon:
                    print(f"❌ ERROR: Coupon '{coupon_code}' not found in database")
                    flash(f"❌ Invalid coupon code: {coupon_code}", "danger")
                    return redirect(url_for('billing', table_no=selected_table_no))

                print(f"✅ Coupon found!")
                print(f"   Type: {coupon.discount_type}")
                print(f"   Value: {coupon.value}")
                print(f"   Active: {coupon.is_active}")
                print(f"   Uses: {coupon.current_uses}/{coupon.max_uses}")

                # Update order with customer info
                if customer_mobile:
                    selected_order.customer_mobile = customer_mobile
                if customer_name:
                    selected_order.customer_name = customer_name

                # Handle customer creation/lookup
                if customer_mobile:
                    customer = Customer.query.filter_by(phone=customer_mobile).first()
                    if not customer:
                        print(f"📝 Creating new customer: {customer_name or 'Guest'}")
                        customer = Customer(
                            name=customer_name if customer_name else "Guest", 
                            phone=customer_mobile, 
                            total_visits=0, 
                            total_spent=0.0
                        )
                        db.session.add(customer)
                        db.session.flush()
                    elif customer_name and customer.name == "Guest":
                        customer.name = customer_name
                        print(f"📝 Updated customer name to: {customer_name}")

                # Validate coupon
                print(f"\n🔍 Validating coupon...")
                is_valid, error_msg = validate_coupon(coupon, selected_order, customer)

                if not is_valid:
                    print(f"❌ Coupon validation failed: {error_msg}")
                    flash(f"❌ {error_msg}", "danger")
                    return redirect(url_for('billing', table_no=selected_table_no))

                print(f"✅ Coupon validation passed!")

                # Calculate discount
                items = json.loads(selected_order.items)
                subtotal_amount = sum(i["qty"] * i["price"] for i in items)
                
                print(f"\n💰 Calculating discount...")
                print(f"   Subtotal: ₹{subtotal_amount}")
                
                discount = calculate_discount(coupon, subtotal_amount, items, customer)
                
                print(f"   Calculated Discount: ₹{discount}")

                if discount <= 0:
                    print(f"❌ Discount is zero or negative")
                    flash("⚠️ This coupon doesn't provide any discount", "warning")
                    return redirect(url_for('billing', table_no=selected_table_no))

                # Apply to order
                print(f"\n💾 Saving to database...")
                print(f"   BEFORE - coupon_code: {selected_order.coupon_code}")
                print(f"   BEFORE - discount_amount: {selected_order.discount_amount}")
                
                selected_order.coupon_code = coupon_code
                selected_order.discount_amount = discount
                coupon.current_uses += 1

                print(f"   AFTER - coupon_code: {selected_order.coupon_code}")
                print(f"   AFTER - discount_amount: {selected_order.discount_amount}")

                db.session.commit()
                
                print(f"✅ Committed to database!")
                
                # Verify save
                db.session.refresh(selected_order)
                print(f"\n✅ VERIFICATION (re-read from DB):")
                print(f"   coupon_code: {selected_order.coupon_code}")
                print(f"   discount_amount: {selected_order.discount_amount}")

                desc = get_discount_description(coupon, customer)
                flash(f"✅ Coupon applied: {desc} - You save ₹{discount:.2f}!", "success")
                
                print(f"\n✅ SUCCESS! Redirecting...")
                print("="*60 + "\n")

                return redirect(url_for('billing', table_no=selected_table_no))

            except Exception as e:
                db.session.rollback()
                print(f"\n❌ EXCEPTION OCCURRED:")
                print(f"   Error: {str(e)}")
                import traceback
                traceback.print_exc()
                flash(f"❌ Error applying coupon: {str(e)}", "danger")
                return redirect(url_for('billing', table_no=selected_table_no))

        # ========================================
        # REMOVE COUPON
        # ========================================
        if request.method == "POST" and "remove_coupon" in request.form:
            try:
                if selected_order.coupon_code:
                    coupon = Coupon.query.filter_by(code=selected_order.coupon_code).first()
                    if coupon and coupon.current_uses > 0:
                        coupon.current_uses -= 1

                    selected_order.coupon_code = None
                    selected_order.discount_amount = 0.0
                    db.session.commit()
                    flash("Coupon removed", "info")

                return redirect(url_for('billing', table_no=selected_table_no))

            except Exception as e:
                db.session.rollback()
                flash(f"Error removing coupon: {str(e)}", "danger")
                return redirect(url_for('billing', table_no=selected_table_no))

        # ========================================
        # GENERATE BILL - WITH WEB SHARE API
        # ========================================
        if request.method == "POST" and "generate_bill" in request.form:
            try:
                customer_mobile = request.form.get("customer_mobile", "").strip()
                customer_name = request.form.get("customer_name", "").strip()

                items = json.loads(selected_order.items) if selected_order.items else []
                subtotal_amount = sum(i["qty"] * i["price"] for i in items)
                discount_amount = selected_order.discount_amount or 0.0
                total_amount = max(0, subtotal_amount - discount_amount)

                if customer_mobile:
                    customer = Customer.query.filter_by(phone=customer_mobile).first()
                    if not customer:
                        customer = Customer(
                            name=customer_name if customer_name else "Guest", 
                            phone=customer_mobile, 
                            total_visits=0, 
                            total_spent=0.0
                        )
                        db.session.add(customer)
                        db.session.flush()
                    elif customer_name and customer.name == "Guest":
                        customer.name = customer_name

                    customer.total_visits += 1
                    customer.total_spent += total_amount
                    customer.last_visit = current_time_ist()

                bill = Bill(
                    order_id=selected_order.id,
                    table_no=selected_order.table_no,
                    customer_id=customer.id if customer else None,
                    subtotal=subtotal_amount,
                    discount=discount_amount,
                    total=total_amount,
                    coupon_code=selected_order.coupon_code,
                    created_by=current_user.id
                )
                db.session.add(bill)

                selected_order.status = "billed"
                if customer_mobile:
                    selected_order.customer_mobile = customer_mobile
                if customer_name:
                    selected_order.customer_name = customer_name

                table = Table.query.filter_by(table_no=selected_table_no).first()
                if table:
                    table.locked = False
                    table.status = "available"
                    table.current_order_id = None

                db.session.add(Log(
                    username=current_user.username,
                    role=current_user.role,
                    action=f"Generated bill #{bill.id} for table {selected_table_no}, Total: ₹{total_amount:.2f}"
                ))
                db.session.commit()

                # Format bill content for printing
                try:
                    from printer_agent import format_bill_content

                    bill_data = {
                        'bill_id': bill.id,
                        'order_id': selected_order.id,
                        'table_no': bill.table_no,
                        'timestamp': bill.created_at,
                        'subtotal_amount': bill.subtotal,
                        'discount_amount': bill.discount,
                        'coupon_code': bill.coupon_code or 'N/A',
                        'total_amount': bill.total,
                        'items': items
                    }

                    bill_content = format_bill_content(bill_data)
                    
                    # Store in session for JavaScript to access
                    session['last_bill_content'] = bill_content
                    session['last_bill_id'] = bill.id
                    
                    flash(f"✅ Bill #{bill.id} generated!", "success")

                except Exception as e:
                    print(f"Print error: {e}")
                    flash(f"✅ Bill #{bill.id} generated!", "success")

                return redirect(url_for('billing'))

            except Exception as e:
                db.session.rollback()
                import traceback
                traceback.print_exc()
                flash(f"Error generating bill: {str(e)}", "danger")
                return redirect(url_for('billing', table_no=selected_table_no))

        # ========================================
        # DISPLAY CALCULATIONS (GET)
        # ========================================
        if selected_order and selected_order.items:
            items = json.loads(selected_order.items)
            subtotal_amount = sum(i["qty"] * i["price"] for i in items)
            discount_amount = selected_order.discount_amount or 0.0
            total_amount = max(0, subtotal_amount - discount_amount)

        if selected_order and selected_order.customer_mobile:
            customer = Customer.query.filter_by(phone=selected_order.customer_mobile).first()

    # Get available coupons
    available_coupons = Coupon.query.filter(
        Coupon.is_active == True,
        Coupon.current_uses < Coupon.max_uses
    ).all()
    
    if selected_order and subtotal_amount > 0:
        available_coupons = [c for c in available_coupons if c.min_amount <= subtotal_amount]

    return render_template(
        "billing.html",
        tables=tables,
        delivery_table=delivery_table,
        selected_table_no=selected_table_no,
        selected_order=selected_order,
        items=items,
        subtotal_amount=subtotal_amount,
        discount_amount=discount_amount,
        total_amount=total_amount,
        customer=customer,
        available_coupons=available_coupons
    )



@app.route('/admin/bills/<int:bill_id>/print')
@login_required
def reprint_bill(bill_id):
    """Reprint a bill to thermal printer."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    bill = Bill.query.get_or_404(bill_id)
    order = Order.query.get(bill.order_id)

    if not order:
        flash("Order not found", "danger")
        return redirect(url_for('admin_bills'))

    try:
        items = json.loads(order.items) if order.items else []
    except:
        items = []

    customer = Customer.query.get(bill.customer_id) if bill.customer_id else None

    if PRINTER_ENABLED:
        try:
            from printer_agent import format_bill_content

            bill_data = {
                'bill_id': bill.id,
                'order_id': order.id,
                'table_no': bill.table_no,
                'timestamp': bill.created_at,
                'subtotal_amount': bill.subtotal,
                'discount_amount': bill.discount,
                'coupon_code': bill.coupon_code or 'N/A',
                'total_amount': bill.total,
                'items': items,
                'customer_name': customer.name if customer else 'Guest',
                'customer_phone': customer.phone if customer else ''
            }

            bill_content = format_bill_content(bill_data)
            success, message = print_to_thermal(bill_content)

            if success:
                flash(f"✅ Bill #{bill.id} reprinted successfully!", "success")
            else:
                flash(f"❌ Print failed: {message}", "danger")

        except Exception as e:
            flash(f"❌ Print error: {str(e)}", "danger")
    else:
        flash("Printer not configured", "warning")

    return redirect(url_for('admin_bill_details', bill_id=bill.id))


# ========================================
# NEW ROUTE: View Bill
# ========================================
@app.route('/bill/view/<int:bill_id>')
@login_required
def view_bill(bill_id):
    """Display bill with manual print button - works everywhere."""
    bill = Bill.query.get_or_404(bill_id)
    order = Order.query.get(bill.order_id)

    if not order:
        flash("Order not found", "danger")
        return redirect(url_for('billing'))

    try:
        items = json.loads(order.items)
    except:
        items = []

    # Generate bill content
    from printer_agent import format_bill_content

    bill_data = {
        'bill_id': bill.id,
        'order_id': order.id,
        'table_no': bill.table_no,
        'timestamp': bill.created_at,
        'subtotal_amount': bill.subtotal,
        'discount_amount': bill.discount,
        'coupon_code': bill.coupon_code or 'N/A',
        'total_amount': bill.total,
        'items': items
    }

    bill_content = format_bill_content(bill_data)

    # Save print job to database
    print_job = PrintJob(order_id=bill.order_id, content=bill_content, status="pending")
    db.session.add(print_job)
    db.session.commit()

    return render_template('view_bill.html', bill=bill, bill_content=bill_content)


# -------------------- ADMIN MENU --------------------
@app.route('/admin/menu', methods=['GET', 'POST'])
@login_required
def admin_menu():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    menu = MenuItem.query.order_by(MenuItem.category.asc(), MenuItem.name.asc()).all()
    categories = sorted(set([item.category for item in menu if item.category]))

    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            category = request.form.get('category', '').strip()
            price_str = request.form.get('price', '').strip()
            available = 'active' in request.form

            if not name or not price_str:
                flash("Name and price are required.", "danger")
                return redirect(url_for('admin_menu'))

            try:
                price = float(price_str)
                if price < 0:
                    flash("Price cannot be negative.", "danger")
                    return redirect(url_for('admin_menu'))
            except ValueError:
                flash("Invalid price format.", "danger")
                return redirect(url_for('admin_menu'))

            new_item = MenuItem(
                name=name,
                category=category,
                price=price,
                available=available,
                created_by=current_user.id
            )

            db.session.add(new_item)
            db.session.add(Log(
                username=current_user.username,
                role=current_user.role,
                action=f"added_menu_item:{name}"
            ))
            db.session.commit()
            flash(f"Menu item '{name}' added successfully!", "success")
            return redirect(url_for('admin_menu'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error adding menu item: {str(e)}", "danger")
            return redirect(url_for('admin_menu'))

    return render_template('admin_menu.html', menu=menu, categories=categories)


@app.route('/admin/menu/toggle/<int:id>')
@login_required
def toggle_item(id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        item = MenuItem.query.get_or_404(id)
        item.available = not item.available
        db.session.add(Log(
            username=current_user.username,
            role=current_user.role,
            action=f"toggled_menu_item:{item.name} -> {'available' if item.available else 'unavailable'}"
        ))
        db.session.commit()
        flash(f"Item '{item.name}' availability updated!", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error toggling item: {str(e)}", "danger")

    return redirect(url_for('admin_menu'))


@app.route('/admin/menu/delete/<int:id>')
@login_required
def delete_item(id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        item = MenuItem.query.get_or_404(id)
        item_name = item.name
        db.session.delete(item)
        db.session.add(Log(
            username=current_user.username,
            role=current_user.role,
            action=f"deleted_menu_item:{item_name}"
        ))
        db.session.commit()
        flash(f"Item '{item_name}' deleted successfully!", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting item: {str(e)}", "danger")

    return redirect(url_for('admin_menu'))

@app.route('/admin/orders', methods=['GET'])
@login_required
def admin_orders():
    """View all orders with filters."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    from datetime import datetime
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', '')

    query = Order.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, "%Y-%m-%d").date()
            start_dt = datetime.combine(date_obj, datetime.min.time())
            end_dt = datetime.combine(date_obj, datetime.max.time())
            query = query.filter(Order.created_at.between(start_dt, end_dt))
        except ValueError:
            pass

    orders = query.order_by(Order.created_at.desc()).all()

    # Statistics
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    served_orders = Order.query.filter_by(status='served').count()
    billed_orders = Order.query.filter_by(status='billed').count()

    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    today_orders = Order.query.filter(Order.created_at.between(today_start, today_end)).count()

    return render_template('admin_orders.html', orders=orders,
        status_filter=status_filter, date_filter=date_filter,
        total_orders=total_orders, pending_orders=pending_orders,
        served_orders=served_orders, billed_orders=billed_orders,
        today_orders=today_orders, filtered_count=len(orders))


@app.route('/admin/orders/<int:order_id>')
@login_required
def admin_order_details(order_id):
    """View single order details."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    order = Order.query.get_or_404(order_id)
    items = json.loads(order.items) if order.items else []
    customer = Customer.query.filter_by(phone=order.customer_mobile).first() if order.customer_mobile else None

    return render_template('admin_order_details.html', order=order, items=items, customer=customer)


@app.route('/admin/orders/export')
@login_required
def export_orders():
    """Export orders to CSV."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        orders = Order.query.order_by(Order.created_at.desc()).all()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Order ID', 'Order Number', 'Table', 'Status', 'Discount', 'Coupon', 'Date'])

        for order in orders:
            items = json.loads(order.items) if order.items else []
            writer.writerow([order.id, order.order_number, order.table_no, order.status,
                           order.discount_amount or 0, order.coupon_code or 'N/A',
                           order.created_at.strftime('%Y-%m-%d %H:%M:%S')])

        data = output.getvalue().encode('utf-8')
        bytes_io = BytesIO(data)
        bytes_io.seek(0)
        return send_file(bytes_io, mimetype='text/csv', as_attachment=True, download_name='orders_export.csv')
    except Exception as e:
        flash(f"Error exporting: {str(e)}", "danger")
        return redirect(url_for('admin_orders'))


# -------------------- ADMIN BILLS --------------------

@app.route('/admin/bills', methods=['GET'])
@login_required
def admin_bills():
    """View all bills with filters."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    from sqlalchemy import func
    from datetime import datetime

    date_filter = request.args.get('date', '')
    min_amount = request.args.get('min_amount', '')

    query = Bill.query

    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, "%Y-%m-%d").date()
            start_dt = datetime.combine(date_obj, datetime.min.time())
            end_dt = datetime.combine(date_obj, datetime.max.time())
            query = query.filter(Bill.created_at.between(start_dt, end_dt))
        except ValueError:
            pass

    if min_amount:
        try:
            query = query.filter(Bill.total >= float(min_amount))
        except ValueError:
            pass

    bills = query.order_by(Bill.created_at.desc()).all()

    # Statistics
    total_revenue = db.session.query(func.sum(Bill.total)).scalar() or 0.0
    total_discount = db.session.query(func.sum(Bill.discount)).scalar() or 0.0
    total_bills = Bill.query.count()
    avg_bill = (total_revenue / total_bills) if total_bills > 0 else 0.0

    filtered_revenue = sum(bill.total for bill in bills)
    filtered_discount = sum(bill.discount for bill in bills)
    filtered_count = len(bills)
    filtered_avg = (filtered_revenue / filtered_count) if filtered_count > 0 else 0.0

    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    today_revenue = db.session.query(func.sum(Bill.total))\
        .filter(Bill.created_at.between(today_start, today_end)).scalar() or 0.0
    today_bills = Bill.query.filter(Bill.created_at.between(today_start, today_end)).count()

    return render_template('admin_bills.html', bills=bills,
        date_filter=date_filter, min_amount=min_amount,
        total_revenue=total_revenue, total_discount=total_discount,
        total_bills=total_bills, avg_bill=avg_bill,
        filtered_revenue=filtered_revenue, filtered_discount=filtered_discount,
        filtered_count=filtered_count, filtered_avg=filtered_avg,
        today_revenue=today_revenue, today_bills=today_bills)


@app.route('/admin/bills/<int:bill_id>')
@login_required
def admin_bill_details(bill_id):
    """View single bill details."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    bill = Bill.query.get_or_404(bill_id)
    order = Order.query.get(bill.order_id)
    items = json.loads(order.items) if order and order.items else []
    customer = Customer.query.get(bill.customer_id) if bill.customer_id else None

    return render_template('admin_bill_details.html', bill=bill, order=order, items=items, customer=customer)


@app.route('/admin/bills/export')
@login_required
def export_bills():
    """Export bills to CSV."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        bills = Bill.query.order_by(Bill.created_at.desc()).all()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Bill ID', 'Order ID', 'Table', 'Subtotal', 'Discount', 'Total', 'Coupon', 'Date'])

        for bill in bills:
            writer.writerow([bill.id, bill.order_id, bill.table_no, bill.subtotal,
                           bill.discount, bill.total, bill.coupon_code or 'N/A',
                           bill.created_at.strftime('%Y-%m-%d %H:%M:%S')])

        data = output.getvalue().encode('utf-8')
        bytes_io = BytesIO(data)
        bytes_io.seek(0)
        return send_file(bytes_io, mimetype='text/csv', as_attachment=True, download_name='bills_export.csv')
    except Exception as e:
        flash(f"Error exporting: {str(e)}", "danger")
        return redirect(url_for('admin_bills'))


# -------------------- ADMIN CUSTOMERS --------------------

@app.route('/admin/customers', methods=['GET'])
@login_required
def admin_customers():
    """View all customers."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    customers = Customer.query.order_by(Customer.total_spent.desc()).all()
    return render_template('admin_customers.html', customers=customers)


@app.route('/admin/customers/<int:customer_id>')
@login_required
def admin_customer_details(customer_id):
    """View single customer details."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    customer = Customer.query.get_or_404(customer_id)
    bills = Bill.query.filter_by(customer_id=customer_id).order_by(Bill.created_at.desc()).all()

    return render_template('admin_customer_details.html', customer=customer, bills=bills)


# -------------------- ADMIN COUPONS --------------------

@app.route('/admin/coupons', methods=['GET'])
@login_required
def admin_coupons():
    """View all coupons."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    coupons = Coupon.query.order_by(Coupon.created_at.desc()).all()
    return render_template('admin_coupons.html', coupons=coupons)


@app.route('/admin/coupons/add', methods=['GET', 'POST'])
@login_required
def add_coupon():
    """Add new coupon."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            code = request.form.get('code', '').strip().upper()
            discount_type = request.form.get('discount_type', '').strip()

            if not code or not discount_type:
                flash("Code and type are required", "danger")
                return redirect(url_for('add_coupon'))

            if Coupon.query.filter_by(code=code).first():
                flash(f"Coupon '{code}' already exists!", "danger")
                return redirect(url_for('add_coupon'))

            coupon = Coupon(code=code, discount_type=discount_type,
                          min_amount=float(request.form.get('min_amount', 0) or 0),
                          max_uses=int(request.form.get('max_uses', 0) or 0) or None,
                          is_active=request.form.get('is_active') == 'on',
                          created_by=current_user.id)

            if discount_type == 'percent':
                coupon.value = float(request.form.get('value', 0))
                coupon.max_discount = float(request.form.get('max_discount', 0) or 0) or None
            elif discount_type == 'flat':
                coupon.value = float(request.form.get('value', 0))
            elif discount_type == 'bogo':
                coupon.bogo_buy_quantity = int(request.form.get('bogo_buy', 1))
                coupon.bogo_get_quantity = int(request.form.get('bogo_get', 1))
                item_ids = request.form.getlist('bogo_items[]')
                coupon.bogo_item_ids = json.dumps([int(id) for id in item_ids if id])
            elif discount_type == 'frequency':
                coupon.frequency_nth_order = int(request.form.get('frequency_nth', 5))
                coupon.frequency_discount_percent = float(request.form.get('frequency_percent', 20))
                coupon.max_discount = float(request.form.get('max_discount', 0) or 0) or None

            db.session.add(coupon)
            db.session.add(Log(username=current_user.username, role=current_user.role,
                             action=f"created_coupon:{code}"))
            db.session.commit()
            flash(f"Coupon '{code}' created!", "success")
            return redirect(url_for('admin_coupons'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    menu_items = MenuItem.query.filter_by(available=True).all()
    return render_template('add_coupon.html', menu_items=menu_items)


@app.route('/admin/coupons/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_coupon(id):
    """Edit existing coupon."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    coupon = Coupon.query.get_or_404(id)

    if request.method == 'POST':
        try:
            coupon.min_amount = float(request.form.get('min_amount', 0) or 0)
            coupon.max_uses = int(request.form.get('max_uses', 0) or 0) or None
            coupon.is_active = request.form.get('is_active') == 'on'

            if coupon.discount_type == 'percent':
                coupon.value = float(request.form.get('value', 0))
                coupon.max_discount = float(request.form.get('max_discount', 0) or 0) or None
            elif coupon.discount_type == 'flat':
                coupon.value = float(request.form.get('value', 0))
            elif coupon.discount_type == 'bogo':
                coupon.bogo_buy_quantity = int(request.form.get('bogo_buy', 1))
                coupon.bogo_get_quantity = int(request.form.get('bogo_get', 1))
                item_ids = request.form.getlist('bogo_items[]')
                coupon.bogo_item_ids = json.dumps([int(id) for id in item_ids if id])
            elif coupon.discount_type == 'frequency':
                coupon.frequency_nth_order = int(request.form.get('frequency_nth', 5))
                coupon.frequency_discount_percent = float(request.form.get('frequency_percent', 20))
                coupon.max_discount = float(request.form.get('max_discount', 0) or 0) or None

            db.session.add(Log(username=current_user.username, role=current_user.role,
                             action=f"edited_coupon:{coupon.code}"))
            db.session.commit()
            flash(f"Coupon '{coupon.code}' updated!", "success")
            return redirect(url_for('admin_coupons'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    menu_items = MenuItem.query.filter_by(available=True).all()
    bogo_item_ids = json.loads(coupon.bogo_item_ids) if coupon.bogo_item_ids else []

    return render_template('edit_coupon.html', coupon=coupon, menu_items=menu_items, bogo_item_ids=bogo_item_ids)


@app.route('/admin/coupons/toggle/<int:id>')
@login_required
def toggle_coupon(id):
    """Activate/deactivate coupon."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        coupon = Coupon.query.get_or_404(id)
        coupon.is_active = not coupon.is_active
        db.session.add(Log(username=current_user.username, role=current_user.role,
                         action=f"toggled_coupon:{coupon.code}"))
        db.session.commit()
        flash(f"Coupon '{coupon.code}' {'activated' if coupon.is_active else 'deactivated'}!", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for('admin_coupons'))


@app.route('/admin/coupons/delete/<int:id>')
@login_required
def delete_coupon(id):
    """Delete coupon."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        coupon = Coupon.query.get_or_404(id)
        code = coupon.code
        db.session.delete(coupon)
        db.session.add(Log(username=current_user.username, role=current_user.role,
                         action=f"deleted_coupon:{code}"))
        db.session.commit()
        flash(f"Coupon '{code}' deleted!", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for('admin_coupons'))


# -------------------- LOGS --------------------
@app.route('/logs', methods=['GET'])
@login_required
def logs():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    selected_date = request.args.get('date')
    selected_role = request.args.get('role')

    query = Log.query

    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
            start_dt = datetime.combine(date_obj, datetime.min.time())
            end_dt = datetime.combine(date_obj, datetime.max.time())
            query = query.filter(Log.timestamp.between(start_dt, end_dt))
        except ValueError:
            flash("Invalid date format", "danger")

    if selected_role:
        query = query.filter_by(role=selected_role)

    logs = query.order_by(Log.timestamp.desc()).all()

    return render_template(
        'logs.html',
        logs=logs,
        selected_date=selected_date,
        selected_role=selected_role
    )


@app.route('/logs/export')
@login_required
def export_logs():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        logs = Log.query.order_by(Log.timestamp.desc()).all()

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'Username', 'Role', 'Action'])
        for log in logs:
            writer.writerow([log.timestamp, log.username, log.role, log.action])

        data = output.getvalue().encode('utf-8')
        bytes_io = BytesIO(data)
        bytes_io.seek(0)

        return send_file(
            bytes_io,
            mimetype='text/csv',
            as_attachment=True,
            download_name='system_logs.csv'
        )
    except Exception as e:
        flash(f"Error exporting logs: {str(e)}", "danger")
        return redirect(url_for('logs'))


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000
            , debug=True
            , threaded=True)