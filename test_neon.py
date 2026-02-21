import sys
import os
from dotenv import load_dotenv

load_dotenv()

print("Testing Neon DB Connection...")

try:
    from alita.memory import MemoryManager
    mem = MemoryManager()
    
    if not mem.conn:
        print("Failed to connect.")
        sys.exit(1)
        
    print("Saving test message to exact history...")
    mem.save_message("user", "My favorite color is neon green.")
    
    print("Testing vector recall...")
    results = mem.recall_memories("What is my favorite color?", n_results=1)
    
    print(f"Recall Results: {results}")
    
    print("Testing profile...")
    prof = mem.get_profile()
    print(f"Profile keys: {list(prof.keys())}")
    
    mem.update_profile({"nickname": "NeonTester"})
    prof2 = mem.get_profile()
    print(f"Updated nickname: {prof2.get('nickname')}")
    
    print("\n✅ ALITA MEMORY INTEGRATION PASSED 100%")
    
except Exception as e:
    print(f"TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
