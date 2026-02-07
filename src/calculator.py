
from datetime import datetime
import re

class ContractCalculator:
    def normalize_date(self, date_str):
        """Normalize date to DD-MM-YYYY."""
        if not date_str or date_str == "Unknown":
            return None
        
        try:
            # Clean string
            date_clean = date_str.replace(",", "").replace("As at", "").replace("As of", "").strip()
            
            # Formats seen: "12/31/2025", "February 3 2026", "2/02/2026"
            if "/" in date_clean:
                dt = datetime.strptime(date_clean, "%m/%d/%Y")
            else:
                dt = datetime.strptime(date_clean, "%B %d %Y")
                
            return dt.strftime("%d-%m-%Y")
        except Exception as e:
            print(f"Date parsing error for {date_str}: {e}")
            return None

    def normalize_contract_month(self, contract_name):
        """Convert 'MAR26', 'March 2026', 'Mar 26' to 'Mar-26'."""
        # Mapping for Excel Month Codes
        months = {
            "JAN": "Jan", "FEB": "Feb", "MAR": "Mar", "APR": "Apr", "MAY": "May", "JUN": "Jun",
            "JUL": "Jul", "AUG": "Aug", "SEP": "Sep", "OCT": "Oct", "NOV": "Nov", "DEC": "Dec",
            "JANUARY": "Jan", "FEBRUARY": "Feb", "MARCH": "Mar", "APRIL": "Apr", "MAY": "May", "JUNE": "Jun",
            "JULY": "Jul", "AUGUST": "Aug", "SEPTEMBER": "Sep", "OCTOBER": "Oct", "NOVEMBER": "Nov", "DECEMBER": "Dec"
        }
        
        try:
            name_upper = contract_name.upper().strip()
            
            # Extract Month Code
            m_code = "UNK"
            for m_full, m_short in months.items():
                if m_full in name_upper:
                    m_code = m_short
                    break
            
            # Extract Year (2 digits)
            # Look for 2026, 26, '26
            year = "26" # Default/Fallback
            y_match = re.search(r"(\d{4})", name_upper)
            if y_match:
                year = y_match.group(1)[-2:]
            else:
                y_match = re.search(r"['\s](\d{2})", name_upper)
                if y_match:
                    year = y_match.group(1)
                elif name_upper[-2:].isdigit(): # e.g. MAR26
                    year = name_upper[-2:]
            
            if m_code != "UNK":
                return f"{m_code}-{year}"
            
            return contract_name # Return original if parsing fails
        except:
            return contract_name

    def get_contract_sort_value(self, contract_name):
        """Return YYYYMM integer for sorting 'Mar-26'."""
        code = self.normalize_contract_month(contract_name)
        # Assuming format MMM-YY e.g. Mar-26
        if len(code) != 6: return 999999
        
        m_map = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
        }
        
        m_str = code[:3]
        y_str = code[4:] 
        
        try:
            year = 2000 + int(y_str)
            month = m_map.get(m_str, 13)
            return year * 100 + month
        except:
            return 999999

    def calculate_hnu_contracts(self, aum, weight, price):
        """
        No of Contracts = (Exposure * Weight) / (Price * 10,000)
        Exposure = AUM * 2
        """
        if not price or price == 0:
            return 0
        
        exposure = aum * 2
        contracts = (exposure * weight) / (price * 10000)
        return int(contracts)

    def calculate_hnd_contracts(self, hnu_contracts):
        """
        HND is inverse. Usually close to negative of HNU if same month?
        SOP says: verify it generates negative number.
        Formula: (Exposure * Weight) / (Price * 10,000)
        But Exposure for Bear is usually -2x? Or just negative output.
        SOP implies HND has its own AUM/Weight, but effectively for same exposure it should be checked.
        We will use the same formula with HND AUM and input.
        """
        return -1 * abs(hnu_contracts) # Force negative as per HND nature

    def calculate_ung_contracts(self, physical_contracts, physical_mv, net_swaps_mv):
        """
        Implied Contracts = (Net Swaps / Physical MV) * Physical Contracts
        Total = Physical + Implied
        """
        if physical_mv == 0:
            return physical_contracts
        
        implied = (net_swaps_mv / physical_mv) * physical_contracts
        return int(physical_contracts + implied)

if __name__ == "__main__":
    calc = ContractCalculator()
    
    # Test Data from Logs
    print(f"Date Test: {calc.normalize_date('February 3 2026')}")
    print(f"Date Test 2: {calc.normalize_date('2/02/2026')}")
    
    # HNU Test
    # AUM ~174M, Weight 1.0, Price ~3.0 (Guess)
    hnu_con = calc.calculate_hnu_contracts(174751156, 1.0, 3.25) # Price is placeholder
    print(f"HNU Contracts (Price 3.25): {hnu_con}")
    
    # UNG Test
    # Physical: 7334, MV: 237M, Swaps: 120M
    ung_con = calc.calculate_ung_contracts(7334, 237401580, 60745272 + 58833818)
    print(f"UNG Contracts: {ung_con}")
