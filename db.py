import os
import json
from app import app
from models import db, User, Table, MenuItem, Coupon, Customer
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

# ✅ Point to the actual Flask DB path (inside /instance)
DB_PATH = os.path.join(app.instance_path, 'database.db')


def init_db():
    # Remove old instance database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"🧹 Removed old database at: {DB_PATH}")

    with app.app_context():
        print("📦 Creating database tables...")
        db.create_all()

        # ========================================
        # CREATE DEFAULT USERS
        # ========================================
        print("\n👥 Creating users...")

        def add_user(username, password, role):
            user = User(
                username=username,
                password=generate_password_hash(password),
                role=role
            )
            db.session.add(user)
            print(f"   ✓ {role.upper()}: {username} / {password}")

        add_user('admin', 'admin123', 'admin')
        add_user('waiter1', 'waiter123', 'waiter')
        add_user('waiter2', 'waiter456', 'waiter')
        add_user('billing1', 'billing123', 'billing')
        add_user('billing2', 'billing456', 'billing')

        # ========================================
        # CREATE RESTAURANT TABLES
        # ========================================
        print("\n🪑 Creating restaurant tables...")

        # Regular tables (1-15)
        for i in range(1, 5):
            t = Table(
                table_no=str(i),
                status='available',
                locked=False,
                is_delivery=False
            )
            db.session.add(t)
        print(f"   ✓ Added tables 1-4")


        # Delivery entry
        delivery = Table(
            table_no='D0',
            status='available',
            locked=False,
            is_delivery=True
        )
        db.session.add(delivery)
        print("   ✓ Added delivery entry D0")

        # ========================================
        # ADD COMPREHENSIVE MENU ITEMS
        # ========================================
        print("\n🍽️ Adding menu items...")

        menu_items = [
            # ===== STARTERS & APPETIZERS =====
            MenuItem(name='Spring Rolls (Veg)', price=129, category='Starters', available=True, created_by=1),
            MenuItem(name='Chicken Wings (6pc)', price=249, category='Starters', available=True, created_by=1),
            MenuItem(name='Paneer Tikka', price=199, category='Starters', available=True, created_by=1),
            MenuItem(name='Fish Fingers', price=279, category='Starters', available=True, created_by=1),
            MenuItem(name='Crispy Corn', price=149, category='Starters', available=True, created_by=1),
            MenuItem(name='Cheese Garlic Bread', price=119, category='Starters', available=True, created_by=1),

            # ===== SHAWARMA (Your specialty!) =====
            MenuItem(name='Chicken Shawarma', price=150, category='Shawarma', available=True, created_by=1),
            MenuItem(name='Mutton Shawarma', price=180, category='Shawarma', available=True, created_by=1),
            MenuItem(name='Paneer Shawarma', price=130, category='Shawarma', available=True, created_by=1),
            MenuItem(name='Falafel Shawarma', price=120, category='Shawarma', available=True, created_by=1),
            MenuItem(name='Chicken Shawarma Platter', price=299, category='Shawarma', available=True, created_by=1),

            # ===== PIZZA =====
            MenuItem(name='Margherita Pizza', price=249, category='Pizza', available=True, created_by=1),
            MenuItem(name='Pepperoni Pizza', price=349, category='Pizza', available=True, created_by=1),
            MenuItem(name='Veggie Supreme Pizza', price=299, category='Pizza', available=True, created_by=1),
            MenuItem(name='BBQ Chicken Pizza', price=399, category='Pizza', available=True, created_by=1),
            MenuItem(name='Paneer Tikka Pizza', price=329, category='Pizza', available=True, created_by=1),

            # ===== BURGERS =====
            MenuItem(name='Classic Veg Burger', price=99, category='Burger', available=True, created_by=1),
            MenuItem(name='Chicken Burger', price=149, category='Burger', available=True, created_by=1),
            MenuItem(name='Cheese Burger', price=179, category='Burger', available=True, created_by=1),
            MenuItem(name='Mushroom Swiss Burger', price=199, category='Burger', available=True, created_by=1),
            MenuItem(name='Double Patty Burger', price=229, category='Burger', available=True, created_by=1),

            # ===== PASTA & NOODLES =====
            MenuItem(name='Pasta Alfredo', price=249, category='Pasta', available=True, created_by=1),
            MenuItem(name='Pasta Arrabiata', price=229, category='Pasta', available=True, created_by=1),
            MenuItem(name='Mac & Cheese', price=199, category='Pasta', available=True, created_by=1),
            MenuItem(name='Hakka Noodles (Veg)', price=149, category='Noodles', available=True, created_by=1),
            MenuItem(name='Hakka Noodles (Chicken)', price=189, category='Noodles', available=True, created_by=1),

            # ===== RICE & BIRYANI =====
            MenuItem(name='Veg Biryani', price=179, category='Rice', available=True, created_by=1),
            MenuItem(name='Chicken Biryani', price=229, category='Rice', available=True, created_by=1),
            MenuItem(name='Mutton Biryani', price=279, category='Rice', available=True, created_by=1),
            MenuItem(name='Egg Fried Rice', price=159, category='Rice', available=True, created_by=1),
            MenuItem(name='Chicken Fried Rice', price=189, category='Rice', available=True, created_by=1),

            # ===== SNACKS & SIDES =====
            MenuItem(name='French Fries', price=89, category='Snacks', available=True, created_by=1),
            MenuItem(name='Peri Peri Fries', price=109, category='Snacks', available=True, created_by=1),
            MenuItem(name='Onion Rings', price=99, category='Snacks', available=True, created_by=1),
            MenuItem(name='Nachos with Cheese', price=149, category='Snacks', available=True, created_by=1),
            MenuItem(name='Chicken Nuggets (6pc)', price=159, category='Snacks', available=True, created_by=1),

            # ===== BEVERAGES - Cold =====
            MenuItem(name='Cold Coffee', price=89, category='Beverage', available=True, created_by=1),
            MenuItem(name='Chocolate Milkshake', price=129, category='Beverage', available=True, created_by=1),
            MenuItem(name='Mango Shake', price=119, category='Beverage', available=True, created_by=1),
            MenuItem(name='Fresh Lime Soda', price=69, category='Beverage', available=True, created_by=1),
            MenuItem(name='Virgin Mojito', price=99, category='Beverage', available=True, created_by=1),
            MenuItem(name='Coca Cola', price=49, category='Beverage', available=True, created_by=1),
            MenuItem(name='Sprite', price=49, category='Beverage', available=True, created_by=1),

            # ===== BEVERAGES - Hot =====
            MenuItem(name='Masala Tea', price=39, category='Hot Beverage', available=True, created_by=1),
            MenuItem(name='Coffee', price=49, category='Hot Beverage', available=True, created_by=1),
            MenuItem(name='Cappuccino', price=89, category='Hot Beverage', available=True, created_by=1),
            MenuItem(name='Hot Chocolate', price=99, category='Hot Beverage', available=True, created_by=1),

            # ===== DESSERTS =====
            MenuItem(name='Chocolate Brownie', price=99, category='Dessert', available=True, created_by=1),
            MenuItem(name='Ice Cream (2 Scoops)', price=79, category='Dessert', available=True, created_by=1),
            MenuItem(name='Gulab Jamun (3pc)', price=59, category='Dessert', available=True, created_by=1),
            MenuItem(name='Chocolate Lava Cake', price=129, category='Dessert', available=True, created_by=1),
        ]

        db.session.add_all(menu_items)
        db.session.flush()
        print(f"   ✓ Added {len(menu_items)} menu items across multiple categories")

        # ========================================
        # ADD SAMPLE CUSTOMERS
        # ========================================
        print("\n👤 Creating sample customers...")

        customers = [
            Customer(name='Rajesh Kumar', phone='9876543210', total_visits=8, total_spent=3500.0, 
                    last_visit=datetime.now() - timedelta(days=2)),
        ]

        db.session.add_all(customers)
        print(f"   ✓ Added {len(customers)} sample customers")

        # ========================================
        # ADD ADVANCED COUPONS
        # ========================================
        print("\n🎟️ Creating coupons...")

        # Get some item IDs for BOGO coupon
        shawarma_items = MenuItem.query.filter_by(category='Shawarma').all()
        shawarma_ids = [item.id for item in shawarma_items[:3]]

        pizza_items = MenuItem.query.filter_by(category='Pizza').all()
        pizza_ids = [item.id for item in pizza_items[:3]]

        coupons = [
            # ===== FLAT DISCOUNTS =====
            Coupon(
                code='FLAT50',
                discount_type='flat',
                value=50.0,
                min_amount=200.0,
                is_active=True,
                max_uses=100,
                current_uses=0,
                created_by=1
            ),
            Coupon(
                code='FLAT100',
                discount_type='flat',
                value=100.0,
                min_amount=500.0,
                is_active=True,
                max_uses=50,
                current_uses=0,
                created_by=1
            ),

            # ===== PERCENT DISCOUNTS =====
            Coupon(
                code='SAVE10',
                discount_type='percent',
                value=10.0,
                min_amount=300.0,
                max_discount=200.0,
                is_active=True,
                max_uses=200,
                current_uses=0,
                created_by=1
            ),
            Coupon(
                code='SAVE20',
                discount_type='percent',
                value=20.0,
                min_amount=500.0,
                max_discount=300.0,
                is_active=True,
                max_uses=100,
                current_uses=0,
                created_by=1
            ),
            Coupon(
                code='VIP25',
                discount_type='percent',
                value=25.0,
                min_amount=1000.0,
                max_discount=500.0,
                is_active=True,
                max_uses=50,
                current_uses=0,
                created_by=1
            ),

            # ===== BOGO OFFERS =====
            Coupon(
                code='BOGO_SHAWARMA',
                discount_type='bogo',
                bogo_buy_quantity=1,
                bogo_get_quantity=1,
                bogo_item_ids=json.dumps(shawarma_ids),
                min_amount=150.0,
                is_active=True,
                max_uses=200,
                current_uses=0,
                created_by=1
            ),
            Coupon(
                code='PIZZA_BOGO',
                discount_type='bogo',
                bogo_buy_quantity=1,
                bogo_get_quantity=1,
                bogo_item_ids=json.dumps(pizza_ids),
                min_amount=300.0,
                is_active=True,
                max_uses=150,
                current_uses=0,
                created_by=1
            ),
            Coupon(
                code='BUY2GET1',
                discount_type='bogo',
                bogo_buy_quantity=2,
                bogo_get_quantity=1,
                bogo_item_ids=json.dumps(shawarma_ids + pizza_ids),
                min_amount=400.0,
                is_active=True,
                max_uses=100,
                current_uses=0,
                created_by=1
            ),

            # ===== FREQUENCY (LOYALTY) COUPONS =====
            Coupon(
                code='LOYAL5',
                discount_type='frequency',
                frequency_nth_order=5,
                frequency_discount_percent=20.0,
                min_amount=200.0,
                max_discount=500.0,
                is_active=True,
                created_by=1
            ),
            Coupon(
                code='LOYAL10',
                discount_type='frequency',
                frequency_nth_order=10,
                frequency_discount_percent=30.0,
                min_amount=300.0,
                max_discount=1000.0,
                is_active=True,
                created_by=1
            ),

            # ===== SPECIAL/SEASONAL =====
            Coupon(
                code='WELCOME50',
                discount_type='flat',
                value=50.0,
                min_amount=150.0,
                is_active=True,
                first_order_only=True,
                max_uses=500,
                current_uses=0,
                created_by=1
            ),
            Coupon(
                code='WEEKENDSPECIAL',
                discount_type='percent',
                value=15.0,
                min_amount=400.0,
                max_discount=250.0,
                is_active=True,
                valid_days='5,6',  # Saturday, Sunday
                max_uses=300,
                current_uses=0,
                created_by=1
            ),
        ]

        db.session.add_all(coupons)
        print(f"   ✓ Added {len(coupons)} coupons")
        print("     - Flat discounts: FLAT50, FLAT100")
        print("     - Percent discounts: SAVE10, SAVE20, VIP25")
        print("     - BOGO offers: BOGO_SHAWARMA, PIZZA_BOGO, BUY2GET1")
        print("     - Loyalty: LOYAL5 (every 5th), LOYAL10 (every 10th)")
        print("     - Special: WELCOME50, WEEKENDSPECIAL")

        db.session.commit()
        print("\n✅ Database initialized successfully with rich sample data!")
        print("\n" + "="*60)
        print("📊 SUMMARY:")
        print("="*60)
        print(f"👥 Users: 5 (1 admin, 2 waiters, 2 billing)")
        print(f"🪑 Tables: 19 (Tables 1-15, VIP V1-V3, Delivery D0)")
        print(f"🍽️ Menu Items: {len(menu_items)}")
        print(f"👤 Sample Customers: {len(customers)}")
        print(f"🎟️ Coupons: {len(coupons)}")
        print("="*60)
        print("\n🔐 Login Credentials:")
        print("   Admin: admin / admin123")
        print("   Waiter: waiter1 / waiter123, waiter2 / waiter456")
        print("   Billing: billing1 / billing123, billing2 / billing456")
        print("="*60)


if __name__ == '__main__':
    # Ensure the instance folder exists before running
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path)

    init_db()