# ts_a.py
from datetime import datetime

def iso8601_to_epoch_seconds(iso_str: str) -> int:
    # Python 3.11+ comprend "Z" directement
    return int(datetime.fromisoformat(iso_str).timestamp())

if __name__ == "__main__":
    import sys
    if not sys.argv[1:]:
        print("Usage: python ts_a.py 2025-05-14T18:00:28.1141208Z"); raise SystemExit(2)
    print(iso8601_to_epoch_seconds(sys.argv[1]))
