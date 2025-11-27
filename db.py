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
            table_no='Parcel',
            status='available',
            locked=False,
            is_delivery=True
        )
        db.session.add(delivery)
        print("   ✓ Added delivery entry D0")

        delivery = Table(
            table_no='Takeaway',
            status='available',
            locked=False,
            is_delivery=True
        )
        db.session.add(delivery)

        # ========================================
        # ADD COMPREHENSIVE MENU ITEMS
        # ========================================
        print("\n🍽️ Adding menu items...")

        menu_items = [
            # ===== SHAWARMA =====
            MenuItem(name='Classic Shawarma', category='Shawarma', price=100.0),
            MenuItem(name='Plain Shawarma', category='Shawarma', price=120.0),
            MenuItem(name='Mexican Shawarma', category='Shawarma', price=140.0),
            MenuItem(name='Turkish Shawarma', category='Shawarma', price=140.0),
            MenuItem(name='American Shawarma', category='Shawarma', price=150.0),
            MenuItem(name='Cheesy Bomb Shawarma', category='Shawarma', price=180.0),
            MenuItem(name='Honey Mustard Shawarma', category='Shawarma', price=140.0),
            MenuItem(name='Full Meat Shawarma', category='Shawarma', price=160.0),
            MenuItem(name='Loaded Shawarma', category='Shawarma', price=180.0),
            MenuItem(name='Burger Shawarma', category='Shawarma', price=150.0),
            MenuItem(name='Moroccan Shawarma', category='Shawarma', price=150.0),
            MenuItem(name='Lays Shawarma', category='Shawarma', price=130.0),
            MenuItem(name='Pani Puri Shawarma', category='Shawarma', price=120.0),
            MenuItem(name='Persion Shawarma', category='Shawarma', price=160.0),
            MenuItem(name='Fire Bird Shawarma', category='Shawarma', price=150.0),

            # ===== BURGERS =====
            MenuItem(name='Chicken Burger', category='Burger', price=120.0),
            MenuItem(name='Beef Burger', category='Burger', price=140.0),
            MenuItem(name='Zinger Burger', category='Burger', price=160.0),
            MenuItem(name='Chicken Cheese Burger', category='Burger', price=140.0),
            MenuItem(name='Beef Cheese Burger', category='Burger', price=160.0),
            MenuItem(name='Double Patty Burger', category='Burger', price=160.0),
            MenuItem(name='Monster Burger', category='Burger', price=180.0),
            
            # ===== STARTERS =====
            MenuItem(name='French Fries', category='Starters', price=90.0),
            MenuItem(name='Peri Peri Fries', category='Starters', price=120.0),
            MenuItem(name='Chicken Dynamite', category='Starters', price=180.0),
            MenuItem(name='Wings Dynamite', category='Starters', price=220.0),
            MenuItem(name='Brownie with Ice Cream', category='Starters', price=100.0),

            # ===== Mojitos =====
            MenuItem(name='Green Apple', category='Mojitos', price=80.0),
            MenuItem(name='Blue Coracao', category='Mojitos', price=80.0),
            MenuItem(name='Passion Fruit', category='Mojitos', price=80.0),
            MenuItem(name='Pineapple', category='Mojitos', price=80.0),

            # ===== LIME =====
            MenuItem(name='Fesh Lime', category='Lime', price=25.0),
            MenuItem(name='Pineapple Lime', category='Lime', price=30.0),
            MenuItem(name='Blue Lime', category='Lime', price=30.0),
            MenuItem(name='Mint Lime', category='Lime', price=30.0),

            # ===== Milkshakes =====
            MenuItem(name='Kitkat', category='Milkshakes', price=100.0),
            MenuItem(name='Brownie', category='Milkshakes', price=120.0),
            MenuItem(name='Oreo', category='Milkshakes', price=90.0),
            MenuItem(name='Tender Coconut', category='Milkshakes', price=90.0),
            MenuItem(name='Peanut Butter', category='Milkshakes', price=120.0),
            MenuItem(name='Avacado', category='Milkshakes', price=110.0),

            # ===== MONSTER SHAKES =====
            MenuItem(name='Kitkat Monster', category='Monster Shakes', price=180.0),
            MenuItem(name='Brownie Monster', category='Monster Shakes', price=180.0),
            MenuItem(name='Oreo Monster', category='Monster Shakes', price=180.0),
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

        Burger_items = MenuItem.query.filter_by(category='Burger').all()
        burger_ids = [item.id for item in Burger_items[:2]]

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
                code='BUZZBURGER',
                discount_type='bogo',
                bogo_buy_quantity=1,
                bogo_get_quantity=1,
                bogo_item_ids=json.dumps(burger_ids),
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
                bogo_item_ids=json.dumps(shawarma_ids + burger_ids),
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