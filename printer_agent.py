import os
import json
import subprocess
import shutil
from datetime import datetime
from models import db, Order, PrintJob, current_time_ist, Bill

PRINTER_ENABLED = True

# RawBT package names (try both common variants)
RAWBT_PACKAGES = [
    'ru.a402d.rawbtprinter',  # Most common
    'com.mmm.rawbt',           # Alternative
]

# ========== UTILITY: Send text directly to RawBT ==========
def send_to_rawbt_direct(text_content):
    """
    Send text content directly to RawBT app via Android intent.
    No file needed!
    
    Returns:
        (success: bool, message: str)
    """
    # Method 1: Try termux-share with text content (BEST METHOD)
    termux_share = shutil.which('termux-share')
    if termux_share:
        try:
            print(f"🔄 Sending directly via termux-share...")
            result = subprocess.run([
                termux_share,
                '-a', 'send',
                '-t', 'text/plain'
            ], input=text_content, text=True, capture_output=True, timeout=3)
            
            if result.returncode == 0:
                return True, "✅ Sent to RawBT (select from share menu)"
            print(f"termux-share error: {result.stderr}")
        except Exception as e:
            print(f"termux-share failed: {e}")
    
    # Method 2: Android AM broadcast with text extra
    am_path = shutil.which('am') or '/system/bin/am'
    if os.path.exists(am_path):
        for package in RAWBT_PACKAGES:
            try:
                print(f"🔄 Trying direct intent to {package}...")
                # Send text directly via intent extra
                result = subprocess.run([
                    am_path, 'start',
                    '-a', 'android.intent.action.SEND',
                    '-t', 'text/plain',
                    '--es', 'android.intent.extra.TEXT', text_content,
                    '-n', f'{package}/.ActivityPrint'
                ], capture_output=True, timeout=3, text=True)
                
                if result.returncode == 0:
                    return True, f"✅ Sent directly to RawBT ({package})"
                print(f"{package} failed: {result.stderr}")
            except Exception as e:
                print(f"{package} error: {e}")
        
        # Try generic share intent (will show app chooser)
        try:
            print(f"🔄 Trying generic share intent...")
            result = subprocess.run([
                am_path, 'start',
                '-a', 'android.intent.action.SEND',
                '-t', 'text/plain',
                '--es', 'android.intent.extra.TEXT', text_content
            ], capture_output=True, timeout=3, text=True)
            
            if result.returncode == 0:
                return True, "✅ Opening share menu - Select RawBT"
        except Exception as e:
            print(f"Generic share failed: {e}")
    
    # Fallback: Save to accessible location as backup
    return save_as_fallback(text_content)


def save_as_fallback(text_content):
    """Fallback: Save to Downloads folder for manual printing."""
    try:
        download_path = '/storage/emulated/0/Download/RestaurantPrints'
        os.makedirs(download_path, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(download_path, f'print_{timestamp}.txt')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        return True, f"📄 Saved to Downloads/RestaurantPrints\nOpen with RawBT to print"
    except Exception as e:
        # Last resort: save to app folder
        os.makedirs('prints', exist_ok=True)
        filepath = f'prints/print_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text_content)
        return True, f"📄 Saved to {filepath}"


# ======= KITCHEN ORDER FUNCTIONS (KOT) =======
def print_kot_rawbt(kot_content, kitchen_number, order_number=None):
    """
    Send KOT directly to RawBT.
    """
    print(f"\n{'='*50}")
    print(f"🍳 PRINTING KOT - Kitchen {kitchen_number} - Order #{order_number}")
    print(f"{'='*50}")
    
    success, message = send_to_rawbt_direct(kot_content)
    
    print(f"Result: {message}")
    print(f"{'='*50}\n")
    
    return success, message


def format_kot_content(order: Order, items: list) -> str:
    """Format KOT content for thermal printer (32 characters wide)."""
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
    lines.append("")  # Extra lines for tear-off
    
    return "\n".join(lines)


# ================ BILL PRINTING FUNCTIONS =====================
def print_bill_rawbt(bill_content, bill_id):
    """Send bill directly to RawBT."""
    print(f"\n{'='*50}")
    print(f"💳 PRINTING BILL - Bill #{bill_id}")
    print(f"{'='*50}")
    
    success, message = send_to_rawbt_direct(bill_content)
    
    print(f"Result: {message}")
    print(f"{'='*50}\n")
    
    return success, message


def format_bill_content(bill_data):
    """Format bill content for thermal printer (32 characters wide)."""
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


def print_bill(bill_id: int):
    """Print a bill by ID."""
    bill = db.session.get(Bill, bill_id)
    if not bill:
        return False, "Bill not found"
    
    order = db.session.get(Order, bill.order_id)
    if not order:
        return False, "Order not found"
    
    try:
        items = json.loads(order.items)
    except Exception:
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


# ============== PRINT JOB SUPPORT ==============
def create_kot_print_job(order_id: int):
    order = Order.query.get(order_id)
    if not order:
        return
    
    try:
        items = json.loads(order.items)
    except Exception:
        items = []
    
    content = format_kot_content(order, items)
    print_job = PrintJob(order_id=order.id, content=content, status='pending')
    db.session.add(print_job)


def create_bill_print_job(bill_id: int):
    bill = db.session.get(Bill, bill_id)
    if not bill:
        return
    
    order = db.session.get(Order, bill.order_id)
    if not order:
        return
    
    try:
        items = json.loads(order.items)
    except Exception:
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


# ======================= SELF-TEST ============================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🔍 RAWBT DIRECT PRINT TEST")
    print("="*60)
    
    print("\n📱 Environment:")
    print(f"   termux-share: {shutil.which('termux-share')}")
    print(f"   am: {shutil.which('am') or '/system/bin/am'}")
    
    # Test KOT
    print("\n" + "="*60)
    print("📝 TEST 1: Kitchen Order Ticket")
    print("="*60)
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
    
    s1, m1 = send_to_rawbt_direct(test_kot)
    print(f"\n✅ KOT Test Result: {m1}")
    
    # Test Bill
    print("\n" + "="*60)
    print("📝 TEST 2: Restaurant Bill")
    print("="*60)
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
    
    s2, m2 = send_to_rawbt_direct(test_bill)
    print(f"\n✅ Bill Test Result: {m2}")
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("="*60)
    print("\nIf share dialog appeared, select RawBT to print!")
    print("If not, check that termux-api is installed:")
    print("  pkg install termux-api")
    print("="*60 + "\n")
