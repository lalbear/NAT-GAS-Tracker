
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ETFScraper:
    def __init__(self, headless=True):
        self.options = Options()
        if headless:
            self.options.add_argument("--headless=new")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--window-size=1920,1080")
        # User agent to avoid detection
        self.options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = None

    def _init_driver(self):
        if not self.driver:
            try:
                # Use standard install
                driver_path = ChromeDriverManager().install()
                
                # Fix for WDM returning notice file on Mac ARM
                if "THIRD_PARTY_NOTICES" in driver_path:
                    driver_path = driver_path.replace("THIRD_PARTY_NOTICES.chromedriver", "chromedriver")

                # Fix permissions for Linux/CI
                import os, stat
                try:
                    st = os.stat(driver_path)
                    os.chmod(driver_path, st.st_mode | stat.S_IEXEC)
                except:
                    pass
                
                # If path is directory, look inside (mac-arm issue)
                if not driver_path.endswith("chromedriver") and "chromedriver" not in driver_path:
                     import os
                     base_dir = os.path.dirname(driver_path) if os.path.isfile(driver_path) else driver_path
                     for root, dirs, files in os.walk(base_dir):
                         if "chromedriver" in files:
                             driver_path = os.path.join(root, "chromedriver")
                             os.chmod(driver_path, 0o755) # Ensure exec
                             break

                self.driver = webdriver.Chrome(service=Service(driver_path), options=self.options)
            except Exception as e:
                logger.error(f"Error initializing Chrome Driver: {e}")
                # Fallback to system chromedriver if manager fails (GitHub Actions has it)
                try:
                    self.driver = webdriver.Chrome(options=self.options)
                except:
                    raise e

    def close(self):
        if self.driver:
            self.driver.quit()

    def get_proshares_data(self, ticker):
        """Scrape BOIL or KOLD data."""
        self._init_driver()
        url = f"https://www.proshares.com/our-etfs/leveraged-and-inverse/{ticker.lower()}"
        logger.info(f"Scraping ProShares {ticker} from {url}")
        
        try:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 20)
            
            # Look for Holdings Section/Table
            # Sometimes need to click a tab, but often loaded. 
            # Subagent simplified: check 'daily holdings' text or table
            
            # Try to find the specific "Holdings" or "Daily Holdings" tab if not visible
            try:
                holdings_tab = self.driver.find_element(By.XPATH, "//li[contains(., 'Holdings')]")
                holdings_tab.click()
                time.sleep(2)
            except:
                logger.info("Holdings tab not found or not clickable, assuming table is present.")

            # Find As Of Date
            # Selector derived from subagent: .fund-detail-table-holdings .container
            # Or general search for "as of"
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            # Look for "Holdings as of" specifically or date near table
            date_match = re.search(r"Holdings as of\s+(\d{1,2}/\d{1,2}/\d{4})", page_text, re.IGNORECASE)
            if not date_match:
                 date_match = re.search(r"as of\s+(\d{1,2}/\d{1,2}/\d{4})", page_text, re.IGNORECASE)
            
            as_of_date = date_match.group(1) if date_match else "Unknown"

            # Find Natural Gas Future Rows
            # The table class is typically .holdings-table or similar
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            contracts = []
            
            for row in rows:
                text = row.text
                if "NATURAL GAS FUTR" in text.upper():
                    cols = row.find_elements(By.TAG_NAME, "td")
                    # Usually: [Name, ..., Shares/Contracts, ...]
                    # We need to be careful with column indices. 
                    # Subagent said: Ticker/Desc, Shares/Contracts
                    
                    # Heuristic: Find the column that looks like a number (contracts)
                    # and the column that has the Future Name
                    contract_name = text.split("NATURAL GAS FUTR")[1].split()[0] # e.g. MAR26
                    # Clean up date part if needed
                    
                    # Find number in columns
                    # Find number in columns
                    possible_contracts = []
                    for col in cols:
                        col_text = col.text.strip()
                        # Clean up val
                        val_clean = col_text.replace(",", "").replace("$", "")
                        
                        # Handle Parenthesis for Negative (e.g. (100) -> -100)
                        multiplier = 1
                        if "(" in val_clean and ")" in val_clean:
                            val_clean = val_clean.replace("(", "").replace(")", "")
                            multiplier = -1
                            
                        if val_clean.isdigit():
                            val = int(val_clean) * multiplier
                            # Filter: Contracts are usually small integers (< 1,000,000), Exposure is usually large (>$1M)
                            # Exception: Small ETFs. But typically Contracts < Exposure.
                            # Also, exposure is usually currency, contracts is int.
                            # We pick the smaller integer that is non-zero, usually.
                            
                            # Heuristic: If abs(val) < 1000000, likely contracts.
                            if 0 < abs(val) < 1000000:
                                possible_contracts.append(val)
                    
                    if possible_contracts:
                        # Take the first one found, or the one that seems most reasonable?
                        # Usually Shares/Contracts is the first numeric column after Name.
                        contract_count = possible_contracts[0]
                        
                        contracts.append({
                            "ticker": ticker,
                            "contract_month": contract_name, # Needs normalization later
                            "count": contract_count
                        })
                        # break # Don't break, might be multiple? No, one row per future per month usually.
                        pass
            
            return {"date": as_of_date, "contracts": contracts}

        except Exception as e:
            logger.error(f"Error scraping {ticker}: {e}")
            return None

    def get_betapro_data(self, ticker):
        """Scrape HNU or HND data."""
        self._init_driver()
        # BetaPro redirects to betapro.ca
        url = f"https://betapro.ca/product/{ticker.lower()}"
        logger.info(f"Scraping BetaPro {ticker} from {url}")

        try:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 15)

            # Disclaimer Check
            try:
                accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'I Accept')] | //button[contains(text(), 'I Accept')]")))
                accept_btn.click()
                logger.info("Accepted disclaimer")
                time.sleep(2)
            except:
                logger.info("No disclaimer found or already accepted")

            # Get AUM from 'Product Facts'
            # Click Product Facts tab if needed, but usually visible or in the DOM
            try:
                facts_tab = self.driver.find_element(By.XPATH, "//li[contains(., 'Product Facts')]")
                facts_tab.click()
                time.sleep(1)
            except:
                pass

            aum_element = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Net Assets')]/following-sibling::*")
            # Problem: Text is '174751156\nAs at January 30 2026'
            aum_text = aum_element.text.split("\n")[0] # Take first line only
            aum_str = aum_text.replace("$", "").replace(",", "").strip()
            aum = float(aum_str) if aum_str else 0.0

            # Get Holdings Weights
            try:
                # Try clicking Holdings tab using JS to avoid interception
                holdings_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Holdings')] | //li[contains(., 'Holdings')]")))
                self.driver.execute_script("arguments[0].click();", holdings_tab)
                logger.info("Clicked Holdings tab via JS")
                time.sleep(3) # Wait for content load
            except Exception as e:
                logger.warning(f"Could not click Holdings tab: {e}")
            
            holdings = []
            
            # Find Rows (Divs, not TRs)
            # Structure: div.w-full.flex.justify-between > p.text-sonicSilver (Name), p.text-white (Weight)
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "div.w-full.flex.justify-between")
                logger.info(f"Found {len(rows)} div rows")
                
                for row in rows:
                    try:
                        # Find P tags
                        ps = row.find_elements(By.TAG_NAME, "p")
                        if len(ps) < 2: continue
                        
                        name = ps[0].text.strip()
                        weight_str = ps[1].text.strip().replace("%", "")
                        
                        if not name or not weight_str: continue
                        
                        # Filter for Natural Gas
                        if "Natural Gas" in name and "ETF" not in name:
                             holdings.append({
                                "original_name": name,
                                "weight": float(weight_str) / 100
                             })
                    except Exception as row_e:
                        continue
            except Exception as e:
                logger.error(f"Error parsing HNU rows: {e}")

            # Date usually found near "As at" - Holdings date is specific
            # Look for date in the holdings section header or near Top Holdings
            # The subagent said: <h2>Top Holdings</h2> <p>As at ...</p>
            try:
                holdings_header = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Top Holdings')]")
                # Look at siblings or text nearby
                header_text = holdings_header.find_element(By.XPATH, "./following-sibling::p").text
                date_str = header_text.replace("As at", "").strip()
            except:
                # Fallback
                date_match = re.search(r"As at\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})", self.driver.page_source)
                date_str = date_match.group(1) if date_match else "Unknown"

            return {
                "date": date_str,
                "aum": aum,
                "holdings": holdings
            }

        except Exception as e:
            logger.error(f"Error scraping {ticker}: {e}")
            return None

    def get_uscf_ung_data(self):
        """Scrape UNG data (Futures + Swaps)."""
        self._init_driver()
        url = "https://www.uscfinvestments.com/holdings/ung"
        logger.info(f"Scraping UNG from {url}")

        try:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 20)
            time.sleep(5) 
            
            # As Of Date
            try:
                date_el = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'As of')]")))
                date_text = date_el.text
                match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", date_text)
                as_of_date = match.group(1) if match else "Unknown"
            except:
                match = re.search(r"As of\s+(\d{1,2}/\d{1,2}/\d{4})", self.driver.page_source)
                as_of_date = match.group(1) if match else "Unknown"

            rows = self.driver.find_elements(By.TAG_NAME, "tr")
            logger.info(f"Found {len(rows)} TR elements on UNG page")
            
            physical_data = []
            swap_data = []

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if not cols: continue
                
                col_texts = [c.text.strip() for c in cols]
                name = col_texts[0] # First column usually Security name

                # Helper to find money and int
                def parse_money(s): return float(s.replace("$","").replace(",","")) if "$" in s else 0.0
                def parse_int(s): return int(s.replace(",","")) if s.replace(",","").isdigit() else 0

                if "NATURAL GAS FUTR" in name.upper():
                    # Physical
                    qty = 0
                    mv = 0.0
                    for txt in col_texts:
                        if txt.replace(",", "").isdigit():
                             # Sometimes a bare number is quantity
                             val = parse_int(txt)
                             if val > 100: # Heuristic: Contracts usually > 100
                                 qty = val
                        elif "$" in txt:
                             mv = max(mv, parse_money(txt))
                    
                    physical_data.append({
                        "name": name,
                        "contracts": qty,
                        "market_value": mv
                    })

                elif "TRS " in name.upper():
                    # Swap
                    mv = 0.0
                    for txt in col_texts:
                        if "$" in txt:
                            mv = max(mv, parse_money(txt))
                    
                    
                    swap_data.append({
                        "name": name,
                        "market_value": mv
                    })
            
            return {
                "date": as_of_date,
                "physical": physical_data,
                "swaps": swap_data
            }

        except Exception as e:
            logger.error(f"Error scraping UNG: {e}")
            return None

    def get_unl_prices(self):
        """Scrape UNL Holdings for settlement prices of 12 months."""
        self._init_driver()
        url = "https://www.uscfinvestments.com/holdings/unl"
        logger.info(f"Scraping UNL Prices from {url}")
        
        try:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 20)
            time.sleep(5) # Wait for table
            
            # rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            rows = self.driver.find_elements(By.TAG_NAME, "tr")
            logger.info(f"Found {len(rows)} UNL rows")
            
            prices = {}
            
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if not cols: continue
                col_texts = [c.text.strip() for c in cols]
                
                logger.info(f"UNL Row: {col_texts}")
                name = col_texts[0]
                if "NATURAL GAS" in name.upper():
                    try:
                        month_code = name.split("FUTR")[1].strip() # Mar26
                        
                        # Price is usually in column 2 (0-indexed: Name, Qty, Price, MV)
                        # Log shows: ['NATURAL GAS FUTR Mar26', '39', '3.2370', '$1,262,430.00', 'NGH26']
                        # So Index 2 is 3.2370
                        if len(col_texts) > 2:
                            price_str = col_texts[2]
                            try:
                                val = float(price_str.replace(",", ""))
                                if val < 500:
                                    prices[month_code.upper()] = val
                                    continue
                            except:
                                pass
                        
                        # Fallback: scan for any small float
                        for txt in col_texts:
                            if "$" not in txt: # Exclude MV
                                try:
                                    val = float(txt.replace(",", ""))
                                    if 0.5 < val < 500 and val != float(col_texts[1]): # Not Qty (39) if possible, but price is small
                                        prices[month_code.upper()] = val
                                        break
                                except:
                                    pass
                    except Exception as e:
                        pass
                                
            return prices
                                
            return prices

        except Exception as e:
            logger.error(f"Error scraping UNL: {e}")
            return {}

if __name__ == "__main__":
    # Test run
    scraper = ETFScraper(headless=True)
    
    # print("--- BOIL ---")
    # print(scraper.get_proshares_data("BOIL"))
    
    # print("\n--- HNU ---")
    # print(scraper.get_betapro_data("HNU"))
    
    # print("\n--- UNG ---")
    # print(scraper.get_uscf_ung_data())
    
    print("\n--- UNL Prices ---")
    print(scraper.get_unl_prices())

    scraper.close()
