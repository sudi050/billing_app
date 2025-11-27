import os
import subprocess
from datetime import datetime

# Directory where print files will be saved
PRINT_DIR = "/storage/emulated/0/Download/RestaurantPrints"

def print_bluetooth(content):
    """
    Save print content and auto-open with RawBT.
    Works from Flask background process!
    
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
        
        # Method 1: Try Android Intent (works from background)
        try:
            print("🔄 Attempting to open with Android Intent...")
            result = subprocess.run([
                'am', 'start',
                '-a', 'android.intent.action.VIEW',
                '-d', f'file://{filepath}',
                '-t', 'text/plain',
                '--user', '0'
            ], timeout=5, capture_output=True, text=True)
            
            print(f"   Intent return code: {result.returncode}")
            if result.stdout:
                print(f"   Output: {result.stdout}")
            if result.stderr:
                print(f"   Error: {result.stderr}")
            
            if result.returncode == 0:
                return True, "📱 Opening with RawBT"
        except FileNotFoundError:
            print("   'am' command not found")
        except Exception as e:
            print(f"   Intent failed: {e}")
        
        # Method 2: Try termux-open
        try:
            print("🔄 Attempting termux-open...")
            result = subprocess.run([
                'termux-open',
                filepath
            ], timeout=5, capture_output=True, text=True)
            
            print(f"   termux-open return code: {result.returncode}")
            
            if result.returncode == 0:
                return True, "📱 Opening with RawBT"
        except FileNotFoundError:
            print("   'termux-open' not found")
        except Exception as e:
            print(f"   termux-open failed: {e}")
        
        # Method 3: Try termux-share (requires Termux:API)
        try:
            print("🔄 Attempting termux-share...")
            result = subprocess.run([
                'termux-share',
                '-a', 'send',
                filepath
            ], timeout=5, capture_output=True, text=True)
            
            print(f"   termux-share return code: {result.returncode}")
            
            if result.returncode == 0:
                return True, "📱 Share menu opened"
        except FileNotFoundError:
            print("   'termux-share' not found (install termux-api)")
        except Exception as e:
            print(f"   termux-share failed: {e}")
        
        # Method 4: Try xdg-open (Linux systems)
        try:
            print("🔄 Attempting xdg-open...")
            result = subprocess.run([
                'xdg-open',
                filepath
            ], timeout=5, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, "📱 Opening with default app"
        except FileNotFoundError:
            print("   'xdg-open' not found")
        except Exception as e:
            print(f"   xdg-open failed: {e}")
        
        # If all methods fail, file is still saved
        print("⚠️  Auto-open failed, but file is saved")
        return True, f"📄 Saved: Downloads/RestaurantPrints/{filename}\nOpen manually with file manager"
        
    except Exception as e:
        print(f"❌ Error in print_bluetooth: {e}")
        import traceback
        traceback.print_exc()
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
    
    print("\n📝 Testing print function...")
    success, message = print_bluetooth(test_content)
    
    print(f"\n{'='*60}")
    print(f"Result: {message}")
    print(f"Success: {success}")
    print(f"{'='*60}")
    
    if success:
        print("\n✅ Test completed!")
        print("\nWhat should happen:")

    else:
        print("\n❌ Test failed!")
        print("Check the error messages above")
    
    print("="*60 + "\n")
