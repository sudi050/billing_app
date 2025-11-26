import os
import json
import subprocess
from datetime import datetime
from models import db, Order, PrintJob, current_time_ist, Bill

PRINTER_ENABLED = True

# ========== UTILITY: Direct RawBT printing with fallback ==========
def print_via_rawbt(content, subdir, prefix, identifier=None):
    """
    Try to print directly via RawBT, fallback to saving text file.
    
    Args:
        content: The text content to print
        subdir: Subdirectory under prints/ for fallback
        prefix: Filename prefix for fallback
        identifier: Optional bill/order number for filename
    
    Returns:
        (success: bool, message: str)
    """
    # Method 1: Try direct printing via Android intent (if available)
    try:
        # This uses 'am' (Activity Manager) to send intent to RawBT
        # Note: RawBT package name may vary, adjust if needed
        # Common package: ru.a402d.rawbtprinter or com.mmm.rawbt
        
        # Save temporary file for intent
        temp_file = '/tmp/rawbt_temp.txt'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Try to send print intent
        result = subprocess.run([
            'am', 'start',
            '-n', 'ru.a402d.rawbtprinter/.ActivityPrint',
            '-a', 'android.intent.action.SEND',
            '-t', 'text/plain',
            '--es', 'android.intent.extra.TEXT', content
        ], capture_output=True, timeout=5)
        
        if result.returncode == 0:
            return True, "Printed via RawBT directly"
        
    except Exception as e:
        print(f"Direct RawBT printing failed: {e}")
    
    # Method 2: Try via termux-share (if termux-api installed)
    try:
        # Save temporary file
        temp_file = '/tmp/rawbt_temp.txt'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        result = subprocess.run([
            'termux-share', '-a', 'send', temp_file
        ], capture_output=True, timeout=5)
        
        if result.returncode == 0:
            return True, "Sent to RawBT via share (select RawBT from chooser)"
        
    except Exception as e:
        print(f"termux-share method failed: {e}")
    
    # Fallback: Save as text file
    try:
        directory = os.path.join('prints', subdir)
        os.makedirs(directory, exist_ok=True)
        
        if identifier:
            filename = f"{prefix}_{identifier}.txt"
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{prefix}_{timestamp}.txt"
        
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True, f"Direct print failed - Saved to {filepath} (open with RawBT)"
    except Exception as e:
        return False, f"Error: {e}"

# ======= KITCHEN ORDER FUNCTIONS (KOT, MULTIPLE KITCHENS) =======
def print_kot_rawbt(kot_content, kitchen_number, order_number=None):
    """
    Print KOT directly or save for RawBT manual print.
    
    Args:
        kot_content: Formatted KOT text
        kitchen_number: 1 or 2
        order_number: Optional order number for filename
    """
    subdir = f"kot/kitchen_{kitchen_number}"
    return print_via_rawbt(kot_content, subdir, "kot", order_number)

def format_kot_content(order: Order, items: list) -> str:
    header = f"*** KITCHEN ORDER TICKET ***\n"
    header += "=" * 32 + "\n"
    header += f"Order #: {order.order_number}\n"
    header += f"Table: {order.table_no}\n"
    header += f"Time: {current_time_ist().strftime('%H:%M:%S')}\n"
    header += "=" * 32 + "\n"
    items_content = "QTY  ITEM\n"
    items_content += "-" * 32 + "\n"
    for item in items:
        items_content += f"{item.get('qty', 1):<4} {item.get('name', 'Unknown Item')}\n"
    footer = "\n" + "=" * 32 + "\n"
    footer += "*** NEW ORDER PLACED ***\n"
    return header + items_content + footer

# ================ BILL PRINTING FUNCTIONS =====================
def print_bill_rawbt(bill_content, bill_id):
    """
    Print bill directly or save for RawBT manual print.
    
    Args:
        bill_content: Formatted bill text
        bill_id: Bill number/ID for filename
    """
    return print_via_rawbt(bill_content, "bills", "bill", bill_id)

def format_bill_content(bill_data):
    header = f"*** RESTAURANT BILL ***\n"
    header += "=" * 32 + "\n"
    header += f"Bill ID: {bill_data['bill_id']}\n"
    header += f"Order ID: {bill_data['order_id']}\n"
    header += f"Table: {bill_data['table_no']}\n"
    header += f"Time: {bill_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
    header += "=" * 32 + "\n"
    items_content = "QTY  ITEM                     PRICE\n"
    items_content += "-" * 32 + "\n"
    for item in bill_data['items']:
        line_total = item['price'] * item['qty']
        item_name = item['name'][:20]
        items_content += f"{item['qty']:<4} {item_name:<20} {line_total:>6.2f}\n"
    totals_content = "-" * 32 + "\n"
    totals_content += f"SUBTOTAL:                {bill_data['subtotal_amount']:>8.2f}\n"
    if bill_data['discount_amount'] > 0:
        totals_content += f"DISCOUNT ({bill_data['coupon_code']}):    -{bill_data['discount_amount']:>8.2f}\n"
    totals_content += "=" * 32 + "\n"
    totals_content += f"TOTAL:                   {bill_data['total_amount']:>8.2f}\n"
    totals_content += "=" * 32 + "\n"
    footer = "\nTHANK YOU! PLEASE VISIT AGAIN!\n"
    return header + items_content + totals_content + footer

def print_bill(bill_id: int):
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

# ============== EXISTING SUPPORT (OPTIONAL/KEEP AS NEEDED) ==============
def create_kot_print_job(order_id: int):
    order = Order.query.get(order_id)
    if not order:
        return
    try:
        items = json.loads(order.items)
    except Exception:
        items = []
    content = format_kot_content(order, items)
    print_job = PrintJob(
        order_id=order.id,
        content=content,
        status='pending'
    )
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
    # --- Test KOT for kitchen 1 with order number ---
    test_kot = "*** KOT TEST ***\nOrder #123\nTable: 5\n\n2x Burger\n1x Fries\n"
    s1, m1 = print_kot_rawbt(test_kot, kitchen_number=1, order_number=123)
    print(m1)

    # --- Test Bill print with bill number ---
    test_bill_data = {
        'bill_id': 456,
        'order_id': 888,
        'table_no': "A1",
        'timestamp': datetime.now(),
        'subtotal_amount': 430.0,
        'discount_amount': 30.0,
        'coupon_code': "FEST30",
        'total_amount': 400.0,
        'items': [{'name': 'Burger', 'qty': 2, 'price': 100.0}, {'name': 'Fries', 'qty': 1, 'price': 80.0}]
    }
    test_bill_content = format_bill_content(test_bill_data)
    s2, m2 = print_bill_rawbt(test_bill_content, bill_id=456)
    print(m2)
