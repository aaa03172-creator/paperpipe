
from src.config import load_config
from src.processor import process_daily_slots

def main():
    results = process_daily_slots(ignore_db=True)
    print(results)

if __name__ == "__main__":
    main()
