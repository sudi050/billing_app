import json
from datetime import datetime
from models import db, Order, PrintJob, current_time_ist, Bill

# Import the bluetooth printing function
from bluetooth_printer import print_bluetooth

PRINTER_ENABLED = True

# ========== KOT FUNCTIONS ==========
def format_kot_content(order: Order, items: list) -> str:
    """Format KOT for 58mm thermal printer (32 chars wide)."""
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
    """Print KOT via file-based method."""
    print(f"\n{'='*50}")
    print(f"🍳 PRINTING KOT - Kitchen {kitchen_number} - Order #{order_number}")
    print(f"{'='*50}")
    
    success, message = print_bluetooth(kot_content)
    
    print(f"Result: {message}")
    print(f"{'='*50}\n")
    
    return success, message


# ========== BILL FUNCTIONS ==========
def format_bill_content(bill_data):
    """Format bill for 58mm thermal printer (32 chars wide)."""
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
    """Print bill via file-based method."""
    print(f"\n{'='*50}")
    print(f"💳 PRINTING BILL - Bill #{bill_id}")
    print(f"{'='*50}")
    
    success, message = print_bluetooth(bill_content)
    
    print(f"Result: {message}")
    print(f"{'='*50}\n")
    
    return success, message


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


# ========== PRINT JOB SUPPORT ==========
def create_kot_print_job(order_id: int):
    """Create a KOT print job in database."""
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
    """Create a bill print job in database."""
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
