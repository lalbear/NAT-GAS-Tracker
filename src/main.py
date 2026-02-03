
import os
import logging
import re
from scraper import ETFScraper
from calculator import ContractCalculator
from sheets import SheetManager
from datetime import datetime

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Daily ETF Tracker")
    
    # 1. Initialize Components
    try:
        scraper = ETFScraper() # Headless by default
        calc = ContractCalculator()
        sheet_id = os.environ.get("SHEET_ID")
        sm = SheetManager(sheet_id)
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return

    data = {}
    
    # 2. Scrape Data
    try:
        # A. Prices (UNL) - Needed for Calculations
        logger.info("Scraping UNL Prices...")
        prices = scraper.get_unl_prices()
        logger.info(f"Prices found: {len(prices)}")
        
        # Helper to get price
        def get_price(m_code):
            # Try exact match or normalization
            norm = calc.normalize_contract_month(m_code)
            return prices.get(norm, prices.get(m_code, 3.0))

        # B. BOIL
        logger.info("Scraping BOIL...")
        boil_data = scraper.get_proshares_data("BOIL")
        boil_holdings = []
        if boil_data and boil_data.get('contracts'):
            for c in boil_data['contracts']:
                # c: {ticker, contract_month, count}
                m = calc.normalize_contract_month(c['contract_month'])
                boil_holdings.append({'month': m, 'val': c['count']})
            
            # Sort by Month
            boil_holdings.sort(key=lambda x: calc.get_contract_sort_value(x['month']))
            data['BOIL'] = boil_holdings
        
        # C. KOLD
        logger.info("Scraping KOLD...")
        kold_data = scraper.get_proshares_data("KOLD")
        kold_holdings = []
        if kold_data and kold_data.get('contracts'):
            for c in kold_data['contracts']:
                m = calc.normalize_contract_month(c['contract_month'])
                # KOLD is Inverse/Short. Contracts usually negative exposure.
                # If site returns positive count, treat as negative.
                cnt = c['count']
                kold_holdings.append({'month': m, 'val': -1 * abs(cnt)})
            kold_holdings.sort(key=lambda x: calc.get_contract_sort_value(x['month']))
            data['KOLD'] = kold_holdings

        # D. HNU
        logger.info("Scraping HNU...")
        hnu_data = scraper.get_betapro_data("HNU")
        hnu_holdings = []
        if hnu_data and hnu_data.get('holdings'):
            for holding in hnu_data['holdings']:
                m_code = calc.normalize_contract_month(holding['original_name'])
                price = get_price(m_code)
                # Calculate contracts
                cnt = calc.calculate_hnu_contracts(hnu_data['aum'], holding['weight'], price)
                hnu_holdings.append({'month': m_code, 'val': cnt})
            
            hnu_holdings.sort(key=lambda x: calc.get_contract_sort_value(x['month']))
            data['HNU'] = hnu_holdings

        # E. HND (Inverse HNU)
        logger.info("Scraping HND...")
        hnd_data = scraper.get_betapro_data("HND")
        hnd_holdings = []
        if hnd_data and hnd_data.get('holdings'):
             for holding in hnd_data['holdings']:
                m_code = calc.normalize_contract_month(holding['original_name'])
                price = get_price(m_code)
                # HND is -2x. 
                cnt = calc.calculate_hnu_contracts(hnd_data['aum'], holding['weight'], price)
                hnd_holdings.append({'month': m_code, 'val': -1 * abs(cnt)})
             
             hnd_holdings.sort(key=lambda x: calc.get_contract_sort_value(x['month']))
             data['HND'] = hnd_holdings

        # F. UNG
        logger.info("Scraping UNG...")
        ung_data = scraper.get_uscf_ung_data()
        ung_holdings_map = {} # Aggregate by month
        
        if ung_data:
            # Physical
            phys_total_contracts = 0
            phys_total_mv = 0
            
            for p in ung_data.get('physical', []):
                m = calc.normalize_contract_month(p['name'])
                # Aggregate Physical for same month
                curr = ung_holdings_map.get(m, {'phys_cnt': 0, 'phys_mv': 0, 'swap_mv': 0})
                curr['phys_cnt'] += p['contracts']
                curr['phys_mv'] += p['market_value']
                ung_holdings_map[m] = curr
                
                phys_total_contracts += p['contracts']
                phys_total_mv += p['market_value']

            # Swaps
            # Distribute Swaps to Months? usually UNG swaps are tied to the benchmark (Front month)
            # OR proportional to physical holdings?
            # SOP usually implies Swaps are converted using Average Price or specific underlying price.
            # Simplification: Assign Swaps to the month with largest Physical holding (Front month).
            
            # Find dominant month
            dominant_month = None
            max_phys = -1
            for m, v in ung_holdings_map.items():
                if v['phys_cnt'] > max_phys:
                    max_phys = v['phys_cnt']
                    dominant_month = m
            
            # Sum up Swap MV
            total_swap_mv = sum([s['market_value'] for s in ung_data.get('swaps', [])])
            
            if dominant_month:
                ung_holdings_map[dominant_month]['swap_mv'] += total_swap_mv
            
            # Calculate Total Contracts Per Month
            ung_final = []
            for m, v in ung_holdings_map.items():
                # Form: Physical + (SwapMV / PhysMV * PhysCnt)
                # But wait, PhysMV is specific to that month? Yes.
                # If PhysMV is 0 (Pure Swap?), use Price.
                
                p_cnt = v['phys_cnt']
                p_mv = v['phys_mv']
                s_mv = v['swap_mv']
                
                if p_mv > 0:
                    implied = (s_mv / p_mv) * p_cnt
                    total = p_cnt + implied
                else:
                    # Fallback if no physical: SwapMV / (Price * 10000)
                    price = get_price(m)
                    if price > 0:
                        total = s_mv / (price * 10000)
                    else:
                        total = 0
                
                ung_final.append({'month': m, 'val': int(total)})
            
            ung_final.sort(key=lambda x: calc.get_contract_sort_value(x['month']))
            data['UNG'] = ung_final
            
            # Use UNG Date as primary
            data['date'] = calc.normalize_date(ung_data.get('date'))
        
        # Fallback Date
        if 'date' not in data:
            if hnu_data: data['date'] = calc.normalize_date(hnu_data.get('date'))

        # G. Price Column (Cols V+)
        # We want to log the Price of the contracts held by UNG/BOIL (Usually Front/Next)
        # Find which months are in play
        active_months = set()
        for k in ['UNG', 'BOIL', 'HNU']:
            for h in data.get(k, []):
                active_months.add(h['month'])
        
        # Sort active months
        sorted_active = sorted(list(active_months), key=lambda x: calc.get_contract_sort_value(x))
        # Take top 2 (Front, Next)
        price_list = []
        for m in sorted_active[:2]:
            p = get_price(m)
            price_list.append({'month': m, 'val': p})
        
        data['Price'] = price_list

    except Exception as e:
        logger.error(f"Scraping/Calculation loop error: {e}")
    finally:
        scraper.close()

    # 3. Log Output
    logger.info("FINAL DATA FOR SHEET:")
    logger.info(data)
    
    # 4. Write to Sheet
    if sm.creds: # Only if auth worked
        sm.append_data(data)
    else:
        logger.info("Skipping Sheet Update (No Credentials)")

if __name__ == "__main__":
    main()
