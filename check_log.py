
import os
import datetime

log_file = "daily_trade.log"

if os.path.exists(log_file):
    stats = os.stat(log_file)
    print(f"File size: {stats.st_size} bytes")
    print(f"Last modified: {datetime.datetime.fromtimestamp(stats.st_mtime)}")
    
    with open(log_file, 'rb') as f:
        f.seek(0, 2)  # Seek to end
        size = f.tell()
        f.seek(max(size - 5000, 0)) # Read last 5KB
        data = f.read()
        try:
            print(data.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Error decoding: {e}")
else:
    print("Log file not found.")
