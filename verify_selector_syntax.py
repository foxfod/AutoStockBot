
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import app.core.selector...")
    from app.core.selector import Selector
    print("Successfully imported Selector class.")
    
    print("Checking default_list syntax...")
    sel = Selector()
    # We can't easily check internal variables without instantiating or inspecting source
    # But just importing strict checks syntax.
    
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
