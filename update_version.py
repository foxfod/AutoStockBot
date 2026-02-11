import os
import re
from datetime import datetime

VERSION_FILE = "app/core/version.py"
HISTORY_FILE = "docs/ver_History.md"

def get_current_version():
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'VERSION = "(.*?)"', content)
        if match:
            return match.group(1)
    return None

def update_version_file(new_version):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(f'VERSION = "{new_version}"\n')
    print(f"✅ Updated {VERSION_FILE} to {new_version}")

def append_history(new_version, title, details):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find where to insert (after header)
    # Actually, appending to the end might be easier, but usually history is reverse chronological?
    # The existing file seems to have older versions at top? No, V.20260209 is at top.
    # Wait, line 5 is [v.20260209_010].
    # Recent adds seem to be appended to the bottom based on the file view in step 6?
    # Let's check line 32 [v.20260209_010-05].
    # Line 99 [v.20260210_010-20].
    # So it is CHRONOLOGICAL (Older -> Newer) in the file? 
    # v.20260209_010 is at line 5.
    # v.20260209_010-20 is at line 99.
    # So new versions are appended at the bottom.
    
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n### [{new_version}] {title}\n")
        # Split details by semicolon or newline to make bullet points
        points = details.split(";")
        for p in points:
            if p.strip():
                f.write(f"- {p.strip()}\n")
    
    print(f"✅ Appended history to {HISTORY_FILE}")

def main():
    current_ver = get_current_version()
    if not current_ver:
        print("❌ Could not find current version.")
        return

    print(f"Current Version: {current_ver}")
    
    # Auto-Increment logic: v.YYYYMMDD_010-XX
    # Parse existing
    # Expected format: YYYYMMDD_010-XX
    today_str = datetime.now().strftime("%Y%m%d")
    
    # Auto-Increment logic: YYYYMMDD_010-XX
    try:
        parts = current_ver.split("-")
        base_ver = parts[0] # YYYYMMDD_010
        suffix = int(parts[1])
        
        current_date = base_ver.split("_")[0]
        
        if current_date == today_str:
            new_suffix = suffix + 1
            new_ver = f"{base_ver}-{new_suffix:02d}"
        else:
            # New Day -> Reset suffix? Or keep global counter?
            # User wants to track history, so maybe reset suffix for new day makes sense?
            # But the existing `20260210_010-20` implies global counter.
            # If date changes, let's reset to 01? Or keep counting?
            # If we reset, we lose global order unless we rely on date.
            # Let's start with 01 for new day for clarity.
            new_ver = f"{today_str}_010-01"
            
    except Exception as e:
        print(f"⚠️ Error parsing version '{current_ver}': {e}")
        print("Defaulting to new day start.")
        new_ver = f"{today_str}_010-01"

    print(f"New Version: {new_ver}")
    
    # Input Description
    try:
        # Use simple input for now. If running via bat, might need arguments.
        # But bat calls python directly in console, so input works.
        print("\n[한글 입력 가능]")
        title = input("변경 사항 제목 (Title): ").strip()
        if not title: title = "자동 업데이트"
        
        details = input("상세 내용 (세미콜론 ; 으로 구분): ").strip()
        
        # Update Files
        update_version_file(new_ver)
        append_history(new_ver, title, details)
        
        # Log for commit message
        with open(".commit_msg", "w", encoding="utf-8") as f:
            f.write(f"[{new_ver}] {title}")
            
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user.")
        return

if __name__ == "__main__":
    main()
