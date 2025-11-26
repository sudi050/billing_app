# print_helper.py
from models import db, Order, PrintJob, current_time_ist, Bill
import json

def format_kot_content(order: Order, items: list) -> str:
    """Formats the Kitchen Order Ticket content."""
    
    # Simple ASCII receipt formatting
    # Note: Character width is limited for typical thermal printers
    
    header = f"*** KITCHEN ORDER TICKET ***\n"
    header += "=" * 32 + "\n"
    header += f"Order #: {order.order_number}\n"
    header += f"Table: {order.table_no}\n"
    header += f"Time: {current_time_ist().strftime('%H:%M:%S')}\n"
    header += "=" * 32 + "\n"
    
    items_content = "QTY  ITEM\n"
    items_content += "-" * 32 + "\n"
    
    for item in items:
        # Format: QTY ITEM_NAME
        items_content += f"{item.get('qty', 1):<4} {item.get('name', 'Unknown Item')}\n"
        
    footer = "\n" + "=" * 32 + "\n"
    footer += "*** NEW ORDER PLACED ***\n"
    
    return header + items_content + footer

def create_kot_print_job(order_id: int):
    """Generates and saves a KOT PrintJob for a given order."""
    order = Order.query.get(order_id)
    if not order:
        return
        
    try:
        items = json.loads(order.items)
    except Exception:
        items = []

    content = format_kot_content(order, items)
    
    # Save print job to the database
    print_job = PrintJob(
        order_id=order.id,
        content=content,
        status='pending'
    )
    db.session.add(print_job)
    # Note: Session commit is handled by the calling route for atomicity

def format_bill_content(bill_data: dict) -> str:
    """Formats the customer bill content."""
    
    # Simple ASCII receipt formatting
    header = f"*** RESTAURANT BILL ***\n"
    header += "=" * 32 + "\n"
    header += f"Bill ID: {bill_data['bill_id']}\n"
    header += f"Order ID: {bill_data['order_id']}\n"
    header += f"Table: {bill_data['table_no']}\n"
    header += f"Time: {bill_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
    header += "=" * 32 + "\n"
    
    # Items Section
    items_content = "QTY  ITEM                     PRICE\n"
    items_content += "-" * 32 + "\n"
    for item in bill_data['items']:
        line_total = item['price'] * item['qty']
        item_name = item['name']
        items_content += f"{item['qty']:<4} {item_name:<20} {line_total:>6.2f}\n"
    
    # Totals Section
    totals_content = "-" * 32 + "\n"
    totals_content += f"SUBTOTAL:                {bill_data['subtotal_amount']:>8.2f}\n"
    
    if bill_data['discount_amount'] > 0:
        totals_content += f"DISCOUNT ({bill_data['coupon_code']}):    -{bill_data['discount_amount']:>8.2f}\n"
    
    totals_content += "=" * 32 + "\n"
    totals_content += f"TOTAL:                   {bill_data['total_amount']:>8.2f}\n"
    totals_content += "=" * 32 + "\n"
    
    footer = "\n"
    footer += "THANK YOU! PLEASE VISIT AGAIN!\n"
    
    return header + items_content + totals_content + footer


def create_bill_print_job(bill_id: int):
    """Retrieves Bill data and generates a printable Bill PrintJob."""
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
    
    # Save print job to the database
    print_job = PrintJob(order_id=bill.order_id, content=content, status="pending")
    db.session.add(print_job)

