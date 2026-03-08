
from src.scraper import ETFScraper
from selenium.webdriver.common.by import By
import logging

logging.basicConfig(level=logging.INFO)

def debug_kold():
    scraper = ETFScraper(headless=True)
    scraper._init_driver()
    
    url = "https://www.proshares.com/our-etfs/leveraged-and-inverse/kold"
    print(f"Accessing {url}...")
    
    try:
        scraper.driver.get(url)
        print("Page accessed.")
        
        # Check text
        body = scraper.driver.find_element(By.TAG_NAME, "body").text
        if "NATURAL GAS" not in body.upper():
            print("WARNING: 'NATURAL GAS' not found in page body.")
        
        # Dump table rows
        rows = scraper.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        print(f"Found {len(rows)} rows.")
        
        for i, row in enumerate(rows):
            text = row.text
            if "NATURAL GAS" in text.upper():
                print(f"ROW {i}: {text}")
                cols = row.find_elements(By.TAG_NAME, "td")
                col_vals = [c.text.replace("\n", " ") for c in cols]
                print(f"  COLS: {col_vals}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    debug_kold()
