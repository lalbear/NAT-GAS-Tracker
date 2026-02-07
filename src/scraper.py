
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
            
            # Try to find the specific "Holdings" or "Daily Holdings" tab if not visible
            try:
                holdings_tab = self.driver.find_element(By.XPATH, "//li[contains(., 'Holdings')]")
                holdings_tab.click()
                time.sleep(2)
            except:
                logger.info("Holdings tab not found or not clickable, assuming table is present.")

            # Find As Of Date
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            date_match = re.search(r"Holdings as of\s+(\d{1,2}/\d{1,2}/\d{4})", page_text, re.IGNORECASE)
            if not date_match:
                 date_match = re.search(r"as of\s+(\d{1,2}/\d{1,2}/\d{4})", page_text, re.IGNORECASE)
            
            as_of_date = date_match.group(1) if date_match else "Unknown"

            # Locate Table and Headers
            # We need to find the specific table that contains "Shares/Contracts" in header
            target_table = None
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            
            for tbl in tables:
                if "Shares/Contracts" in tbl.text or "Exposure" in tbl.text:
                    target_table = tbl
                    break
            
            if not target_table:
                logger.error(f"Could not find Holdings table for {ticker}")
                return None

            # Parse Headers to find indices
            headers = target_table.find_elements(By.TAG_NAME, "th")
            header_map = {h.text.strip().upper(): i for i, h in enumerate(headers)}
            
            # Map known headers to indices
            # KOLD: Exposure Weight | Ticker | Description | Exposure Value | Market Value | Shares/Contracts | SEDOL
            # BOIL: Name | ... | Shares/Contracts ? (Need to be flexible)
            
            desc_idx = -1
            contracts_idx = -1
            
            # Find Description Column
            for key in ["DESCRIPTION", "NAME", "SECURITY NAME", "TICKER"]:
                if key in header_map:
                    desc_idx = header_map[key]
                    break
            
            # Find Contracts Column
            for key in ["SHARES/CONTRACTS", "SHARES", "CONTRACTS"]:
                if key in header_map:
                    contracts_idx = header_map[key]
                    break
            
            if desc_idx == -1 or contracts_idx == -1:
                logger.warning(f"Could not map columns via headers. Header Map: {header_map}")
                # Fallback: KOLD specific 
                if ticker.upper() == "KOLD":
                    # KOLD typically: Description is idx 2, Contracts is idx 5
                    desc_idx = 2
                    contracts_idx = 5
                else: 
                     # BOIL typically: Name idx 0, Contracts idx 2
                    desc_idx = 0
                    contracts_idx = 2

            # Parse Rows
            rows = target_table.find_elements(By.CSS_SELECTOR, "tbody tr")
            contracts = []
            
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if not cols or len(cols) <= max(desc_idx, contracts_idx): continue
                
                desc_text = cols[desc_idx].text.strip().upper()
                
                if "NATURAL GAS FUTR" in desc_text:
                    # Extract contract name (e.g. MAR26)
                    try:
                        contract_name = desc_text.split("NATURAL GAS FUTR")[1].strip().split()[0]
                    except:
                        contract_name = desc_text
                        
                    # Extract Contracts Count
                    val_text = cols[contracts_idx].text.strip()
                    # Clean -26,090 -> 26090
                    clean_val = val_text.replace(",", "").replace("$", "")
                    
                    try:
                        # Handle Parenthesis
                        if "(" in clean_val and ")" in clean_val:
                            clean_val = "-" + clean_val.replace("(", "").replace(")", "")
                        
                        val = int(float(clean_val)) # Use float first to be safe
                        
                        # Add to list
                        contracts.append({
                            "ticker": ticker,
                            "contract_month": contract_name,
                            "count": val
                        })
                    except:
                        logger.warning(f"Failed to parse contract value '{val_text}' for {contract_name}")
                        continue

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
