import os
import json
import subprocess
from datetime import datetime
from models import db, Order, PrintJob, current_time_ist, Bill

PRINTER_ENABLED = True
PRINT_DIR = "/storage/emulated/0/Download/RestaurantPrints"


# ========== CORE PRINTING FUNCTION ==========
def print_bluetooth_rawbt(text_content):
    """
    Save to file and open with RawBT via termux-share.
    No python-escpos needed - works 100% in Termux!
    
    Returns:
        (success: bool, message: str)
    """
    try:
        # Create directory
        os.makedirs(PRINT_DIR, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%H%M%S')
        filename = f"print_{timestamp}.txt"
        filepath = os.path.join(PRINT_DIR, filename)
        
        # Save content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        # Set readable permissions
        os.chmod(filepath, 0o644)
        
        print(f"✅ Saved: {filepath}")
        
        # Open with termux-share (shows RawBT in share menu)
        try:
            subprocess.Popen(['termux-share', filepath])
            return True, "📱 Share menu opening - Select RawBT"
        except FileNotFoundError:
            print("⚠️  termux-share not found")
            return True, f"📄 File saved: {filename}\nOpen manually with RawBT"
        except Exception as e:
            print(f"⚠️  termux-share error: {e}")
            return True, f"📄 File saved: {filename}\nOpen manually with RawBT"
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, f"❌ Error: {str(e)}"


# ========== KOT FUNCTIONS ==========
def format_kot_content(order, items):
    """Format KOT for 58mm thermal printer (32 chars wide)"""
    lines = []
    lines.append("*** KITCHEN ORDER TICKET ***")
    lines.append("=" * 32)
    lines.append(f"Order #: {order.order_number}")
    lines.append(f"Table: {order.table_no}")
    lines.append(f"Time: {current_time_ist().strftime('%H:%M:%S')}")
    lines.append("=" * 32)
    lines.append("")
    lines.append("QTY  ITEM")
    lines.append("-" * 32)
    
    for item in items:
        qty = item.get('qty', 1)
        name = item.get('name', 'Unknown Item')
        if len(name) > 27:
            lines.append(f"{qty:<4} {name[:27]}")
            lines.append(f"     {name[27:]}")
        else:
            lines.append(f"{qty:<4} {name}")
    
    lines.append("")
    lines.append("=" * 32)
    lines.append("*** PREPARE THIS ORDER ***")
    lines.append("")
    lines.append("")
    lines.append("")
    
    return "\n".join(lines)


def print_kot_rawbt(kot_content, kitchen_number, order_number=None):
    """Print KOT via RawBT"""
    print(f"\n{'='*50}")
    print(f"🍳 PRINTING KOT - Kitchen {kitchen_number} - Order #{order_number}")
    print(f"{'='*50}")
    
    success, message = print_bluetooth_rawbt(kot_content)
    
    print(f"Result: {message}")
    print(f"{'='*50}\n")
    
    return success, message


# ========== BILL FUNCTIONS ==========
def format_bill_content(bill_data):
    """Format bill for 58mm thermal printer (32 chars wide)"""
    lines = []
    lines.append("      RESTAURANT BILL")
    lines.append("=" * 32)
    lines.append(f"Bill #: {bill_data['bill_id']}")
    lines.append(f"Order #: {bill_data['order_id']}")
    lines.append(f"Table: {bill_data['table_no']}")
    lines.append(f"Time: {bill_data['timestamp'].strftime('%d-%b-%Y %H:%M')}")
    lines.append("=" * 32)
    lines.append("")
    lines.append("QTY  ITEM              PRICE")
    lines.append("-" * 32)
    
    for item in bill_data['items']:
        qty = item['qty']
        name = item['name'][:15]
        price = item['price']
        line_total = price * qty
        lines.append(f"{qty:<4} {name:<15} {line_total:>7.2f}")
    
    lines.append("")
    lines.append("-" * 32)
    lines.append(f"SUBTOTAL:            {bill_data['subtotal_amount']:>10.2f}")
    
    if bill_data['discount_amount'] > 0:
        coupon = bill_data['coupon_code'][:8]
        lines.append(f"DISCOUNT ({coupon})    -{bill_data['discount_amount']:>10.2f}")
    
    lines.append("=" * 32)
    lines.append(f"TOTAL:               {bill_data['total_amount']:>10.2f}")
    lines.append("=" * 32)
    lines.append("")
    lines.append("    THANK YOU!")
    lines.append("  PLEASE VISIT AGAIN!")
    lines.append("")
    lines.append("")
    lines.append("")
    
    return "\n".join(lines)


def print_bill_rawbt(bill_content, bill_id):
    """Print bill via RawBT"""
    print(f"\n{'='*50}")
    print(f"💳 PRINTING BILL - Bill #{bill_id}")
    print(f"{'='*50}")
    
    success, message = print_bluetooth_rawbt(bill_content)
    
    print(f"Result: {message}")
    print(f"{'='*50}\n")
    
    return success, message


def print_bill(bill_id):
    """Print a bill by ID"""
    bill = db.session.get(Bill, bill_id)
    if not bill:
        return False, "Bill not found"
    
    order = db.session.get(Order, bill.order_id)
    if not order:
        return False, "Order not found"
    
    try:
        items = json.loads(order.items)
    except:
        items = []
    
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
    
    content = format_bill_content(bill_data)
    return print_bill_rawbt(content, bill.id)


# ========== PRINT JOB SUPPORT ==========
def create_kot_print_job(order_id):
    """Create KOT print job in database"""
    order = Order.query.get(order_id)
    if not order:
        return
    
    try:
        items = json.loads(order.items)
    except:
        items = []
    
    content = format_kot_content(order, items)
    print_job = PrintJob(order_id=order.id, content=content, status='pending')
    db.session.add(print_job)


def create_bill_print_job(bill_id):
    """Create bill print job in database"""
    bill = db.session.get(Bill, bill_id)
    if not bill:
        return
    
    order = db.session.get(Order, bill.order_id)
    if not order:
        return
    
    try:
        items = json.loads(order.items)
    except:
        items = []
    
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
    
    content = format_bill_content(bill_data)
    print_job = PrintJob(order_id=bill.order_id, content=content, status="pending")
    db.session.add(print_job)


# ========== TEST ==========
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🖨️  RAWBT PRINTER TEST")
    print("="*60)
    print(f"\n📁 Save location: {PRINT_DIR}")
    
    # Test KOT
    print("\n📝 TEST 1: Kitchen Order Ticket")
    test_kot = """*** KITCHEN ORDER TICKET ***
================================
Order #: 123
Table: 5
Time: 14:30:25
================================

QTY  ITEM
--------------------------------
2    Burger
1    Fries
3    Coke

================================
*** PREPARE THIS ORDER ***


"""
    
    s1, m1 = print_bluetooth_rawbt(test_kot)
    print(f"\n{'✅' if s1 else '❌'} Result: {m1}")
    
    # Test Bill
    print("\n📝 TEST 2: Restaurant Bill")
    test_bill = """      RESTAURANT BILL
================================
Bill #: 456
Order #: 888
Table: A1
Time: 27-Nov-2025 14:30
================================

QTY  ITEM              PRICE
--------------------------------
2    Burger             200.00
1    Fries               80.00
2    Coke               100.00

--------------------------------
SUBTOTAL:               380.00
DISCOUNT (FEST30)       -30.00
================================
TOTAL:                  350.00
================================

    THANK YOU!
  PLEASE VISIT AGAIN!


"""
    
    s2, m2 = print_bluetooth_rawbt(test_bill)
    print(f"\n{'✅' if s2 else '❌'} Result: {m2}")
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE!")
    print("="*60)
    print("\n📱 If share menu appeared, select RawBT")
    print("📁 If not, check: Downloads/RestaurantPrints/")
    print("="*60 + "\n")
