
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from scraper import ETFScraper
from calculator import ContractCalculator
import logging

logging.basicConfig(level=logging.INFO)

def debug():
    scraper = ETFScraper(headless=True)
    calc = ContractCalculator()
    
    print("Testing UNL Prices Scraping...")
    prices = scraper.get_unl_prices()
    print(f"Scraped Prices: {prices}")
    
    test_months = ["MAR26", "APR26", "MAY26"]
    for m in test_months:
        norm = calc.normalize_contract_month(m)
        print(f"Month: {m} -> Normalized: {norm}")
        print(f"  prices.get('{norm}'): {prices.get(norm)}")
        print(f"  prices.get('{m}'): {prices.get(m)}")
        
    scraper.close()

if __name__ == "__main__":
    debug()
