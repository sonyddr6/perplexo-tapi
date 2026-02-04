import sys
import os
from pathlib import Path

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from token_manager import TokenManager, DEFAULT_TOKENS_DIR, DEFAULT_RAW_COOKIES_FILE

print(f"CWD: {os.getcwd()}")
print(f"Expected tokens dir: {DEFAULT_TOKENS_DIR.absolute()}")
print(f"Expected raw file: {DEFAULT_RAW_COOKIES_FILE}")

raw_path = DEFAULT_TOKENS_DIR / DEFAULT_RAW_COOKIES_FILE
print(f"Checking {raw_path}...")
if raw_path.exists():
    print(f"  File exists! Size: {raw_path.stat().st_size} bytes")
else:
    print(f"  FILE NOT FOUND AT {raw_path}")

tm = TokenManager()
print(f"Accounts loaded: {len(tm.accounts)}")
for acc in tm.accounts:
    print(f" - {acc.get('name')}: {acc.get('session_token')[:10]}...")
