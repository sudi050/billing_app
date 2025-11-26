
import os
import json
from datetime import datetime
from models import db, Order, PrintJob, current_time_ist, Bill

# Try to import printer modules
PRINTER_AVAILABLE = False
BLUETOOTH_AVAILABLE = False

try:
    from escpos.printer import Usb, Network, Serial
    PRINTER_AVAILABLE = True
    print("✓ python-escpos basic modules loaded")
except ImportError as e:
    print(f"⚠️ python-escpos not available: {e}")

try:
    from escpos.printer import Bluetooth
    BLUETOOTH_AVAILABLE = True
    print("✓ Bluetooth printer support loaded")
except ImportError:
    print("⚠️ Bluetooth printer not available (will use file fallback)")

# Configuration
PRINTER_ENABLED = True
BLUETOOTH_PRINTER_MAC = os.environ.get('PRINTER_MAC', '10:22:33:D0:C7:3A')


# ============================================================
# ORIGINAL FUNCTIONS (from your printer_agent.py)
# ============================================================

def format_kot_content(order: Order, items: list) -> str:
    """Formats the Kitchen Order Ticket content."""

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


# ============================================================
# NEW FUNCTIONS (Bluetooth Printing)
# ============================================================

def print_to_thermal(bill_content):
    """
    Print to thermal printer via Bluetooth.
    Falls back to file printing if Bluetooth unavailable.

    Args:
        bill_content: Formatted bill text

    Returns:
        (success: bool, message: str)
    """

    if not PRINTER_ENABLED:
        return False, "Printer disabled in configuration"

    # Method 1: Try Bluetooth if available
    if BLUETOOTH_AVAILABLE:
        try:
            printer = Bluetooth(BLUETOOTH_PRINTER_MAC)
            printer.text(bill_content)
            printer.cut()
            printer.close()
            return True, "Printed to Bluetooth printer"
        except Exception as e:
            print(f"Bluetooth print failed: {e}")
            # Fall through to file method

    # Method 2: Fallback to file printing
    try:
        # Create prints directory if not exists
        os.makedirs('prints', exist_ok=True)

        # Save to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'prints/bill_{timestamp}.txt'

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(bill_content)

        return True, f"Saved to {filename} (Bluetooth unavailable)"

    except Exception as e:
        return False, f"Print failed: {str(e)}"


def print_order_to_kitchen(order_data):
    """
    Print order ticket to kitchen printer.

    Args:
        order_data: Dictionary with order information

    Returns:
        (success: bool, message: str)
    """

    content = []
    content.append("="*32)
    content.append("      KITCHEN ORDER")
    content.append("="*32)
    content.append("")
    content.append(f"Order: #{order_data['order_number']}")
    content.append(f"Table: {order_data['table_no']}")
    content.append(f"Time: {order_data['timestamp'].strftime('%H:%M')}")
    content.append("")
    content.append("-"*32)

    for item in order_data['items']:
        content.append(f"{item['qty']}x {item['name']}")
        if item.get('notes'):
            content.append(f"   Note: {item['notes']}")

    content.append("-"*32)
    content.append("")

    bill_content = "\n".join(content)

    return print_to_thermal(bill_content)


# ============================================================
# TEST FUNCTION
# ============================================================

def test_printer():
    """Test printer connectivity."""
    print("\n" + "="*50)
    print("🖨️  PRINTER TEST")
    print("="*50)

    print(f"\nPrinter enabled: {PRINTER_ENABLED}")
    print(f"Bluetooth available: {BLUETOOTH_AVAILABLE}")
    print(f"Printer MAC: {BLUETOOTH_PRINTER_MAC}")

    if BLUETOOTH_AVAILABLE:
        print("\n✓ Bluetooth printer support loaded")
        print("  Will attempt Bluetooth printing")
    else:
        print("\n⚠️ Bluetooth not available")
        print("  Will save bills to prints/ folder")

    # Test print
    test_bill = {
        'bill_id': 1,
        'order_id': 1,
        'table_no': '1',
        'timestamp': datetime.now(),
        'subtotal_amount': 500.0,
        'discount_amount': 50.0,
        'coupon_code': 'TEST50',
        'total_amount': 450.0,
        'items': [
            {'name': 'Test Item', 'qty': 2, 'price': 250.0}
        ]
    }

    print("\nAttempting test print...")
    content = format_bill_content(test_bill)
    success, message = print_to_thermal(content)

    if success:
        print(f"\n✅ {message}")
    else:
        print(f"\n❌ {message}")

    print("="*50 + "\n")

    return success


if __name__ == '__main__':
    test_printer()