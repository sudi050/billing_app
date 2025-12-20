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
    Save file and send notification with tap action.
    User taps notification → Opens RawBT → Prints automatically!
    
    Returns:
        (success: bool, message: str)
    """
    try:
        # Create directory
        os.makedirs(PRINT_DIR, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%H%M%S')
        filename = f"KOT_{timestamp}.txt"
        filepath = os.path.join(PRINT_DIR, filename)
        
        # Save content to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        # Set readable permissions
        os.chmod(filepath, 0o644)
        
        print(f"✅ Saved: {filepath}")
        
        # Send notification with tap action
        try:
            subprocess.Popen([
                'termux-notification',
                '--id', 'print_job',
                '--title', '🖨️ Print Ready',
                '--content', f'Tap to print {filename}',
                '--action', f'termux-open "{filepath}"',
                '--priority', 'high',
                '--sound'
            ])
            print("✅ Notification sent")
            return True, "📱 Notification sent - Tap to print"
        except FileNotFoundError:
            print("⚠️  termux-notification not found")
            # Fallback to termux-open
            try:
                subprocess.Popen(['termux-open', filepath])
                return True, "📱 Opening with RawBT"
            except:
                return True, f"📄 File saved: {filename}\nOpen manually"
        except Exception as e:
            print(f"⚠️  Notification error: {e}")
            # Fallback to termux-open
            try:
                subprocess.Popen(['termux-open', filepath])
                return True, "📱 Opening with RawBT"
            except:
                return True, f"📄 File saved: {filename}\nOpen manually"
        
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
    """Print KOT via notification"""
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
    """Print bill via notification"""
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
    print("🖨️  NOTIFICATION-BASED PRINTER TEST")
    print("="*60)
    
    test_content = """*** TEST PRINT ***
Notification Method
Tap notification to print!


"""
    
    success, msg = print_bluetooth_rawbt(test_content)
    print(f"\nResult: {msg}")
    
    if success:
        print("\n✅ Check your notification!")
        print("📱 Tap it to open RawBT and print")
    
    print("="*60 + "\n")
