from datetime import time as dtime
from datetime import datetime

def is_time_in_range(start, end, current):
    if start <= end:
        return start <= current <= end
    else: # Crosses midnight
        return start <= current or current <= end

US_SCAN_START = dtime(22, 10)
SCAN_END = dtime(4, 0)
CURRENT_TIME = datetime.now().time()

print(f"Current Time: {CURRENT_TIME}")
print(f"Scan Start: {US_SCAN_START}")
print(f"Scan End: {SCAN_END}")

is_active = is_time_in_range(US_SCAN_START, SCAN_END, CURRENT_TIME)
print(f"Is Scan Active? {is_active}")

if not is_active:
    print("❌ Scanning is disabled because it's past 04:00 AM!")
else:
    print("✅ Scanning should be active.")
