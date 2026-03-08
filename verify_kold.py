from src.scraper import ETFScraper
import logging

logging.basicConfig(level=logging.INFO)

def verify_kold():
    print("Initializing Scraper...")
    scraper = ETFScraper(headless=True)
    
    print("Fetching KOLD Data...")
    try:
        data = scraper.get_proshares_data("KOLD")
        print("\n--- RESULT ---")
        print(data)
        
        if data and data.get('contracts'):
            print(f"Success! Extracted {len(data['contracts'])} contracts.")
            for c in data['contracts']:
                print(f"  - {c['contract_month']}: {c['count']}")
        else:
            print("FAILED: No contracts found.")
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    verify_kold()
