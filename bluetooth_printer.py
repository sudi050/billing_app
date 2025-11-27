import os
import subprocess
from datetime import datetime

# Directory where print files will be saved
PRINT_DIR = "/storage/emulated/0/Download/RestaurantPrints"

def print_bluetooth(content):
    """
    Save print content and open with RawBT.
    Works 100% in Termux - no dependencies!
    
    Returns:
        (success: bool, message: str)
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(PRINT_DIR, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"print_{timestamp}.txt"
        filepath = os.path.join(PRINT_DIR, filename)
        
        # Save content to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Saved: {filepath}")
        
        # Try to auto-open with app chooser
        try:
            result = subprocess.run([
                'termux-open',
                filepath
            ], timeout=3, capture_output=True)
            
            if result.returncode == 0:
                return True, "📱 Opening with RawBT - Select RawBT from menu"
        except Exception as e:
            print(f"termux-open failed: {e}")
        
        # If auto-open fails, return file location
        return True, f"📄 Saved to Downloads/RestaurantPrints/{filename}\nOpen with RawBT to print"
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}"


# Test function
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🖨️  BLUETOOTH PRINTER TEST")
    print("="*60)
    
    test_content = """*** TEST PRINT ***
Restaurant POS System
Termux + RawBT

This is a test receipt.
If you see this, it works!


"""
    
    print("\n📝 Printing test receipt...")
    success, message = print_bluetooth(test_content)
    
    print(f"\n{message}")
    
    if success:
        print("\n" + "="*60)
        print("✅ Test completed!")
        print("="*60)
        print("\nIf app chooser appeared, select RawBT.")
        print("If not, check Downloads/RestaurantPrints folder.")
        print("="*60)
