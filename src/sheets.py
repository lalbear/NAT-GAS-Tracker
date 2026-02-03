
import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class SheetManager:
    def __init__(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.creds = None
        self.service = None
        self._auth()

    def _auth(self):
        """Authenticate using Service Account."""
        sid = os.environ.get("SHEET_ID", "")
        logger.info(f"DEBUG: SHEET_ID length received: {len(sid)}")
        
        # Verify if Key exists
        key_env = os.environ.get("GCP_SA_KEY", "")
        logger.info(f"DEBUG: GCP_SA_KEY length received: {len(key_env)}")
        
        # Print available keys (Obfuscated) to check for Typos (e.g. SECRET_SHEET_ID)
        env_keys = [k for k in os.environ.keys() if "GCP" in k or "SHEET" in k or "SECRET" in k]
        logger.info(f"DEBUG: Relevant Env Vars found: {env_keys}")

        if not self.spreadsheet_id:
            logger.error("SPREADSHEET ID is Missing! Check your 'SHEET_ID' secret.")
            # OPTIONAL: You can hardcode your ID here if Secrets fail
            # self.spreadsheet_id = "YOUR_ACTUAL_ID_HERE"
            return

        try:
            # Check for env var with key content (GitHub Actions)
            if "GCP_SA_KEY" in os.environ:
                key_dict = json.loads(os.environ["GCP_SA_KEY"])
                self.creds = service_account.Credentials.from_service_account_info(
                    key_dict, scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            # Check for local file
            elif os.path.exists("credentials.json"):
                self.creds = service_account.Credentials.from_service_account_file(
                    "credentials.json", scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            else:
                logger.warning("No GCP credentials found (GCP_SA_KEY env or credentials.json)")
                return

            self.service = build('sheets', 'v4', credentials=self.creds)
            logger.info("Authenticated with Google Sheets")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")

    def append_data(self, data_dict):
        """
        Append a new row to 'Daily Holdings (NG ETFs)'.
        Row Format (Columns A-AC approx):
        Date | BOIL (C1 M, C1 V, C2 M, C2 V) | HNU (...) | UNG (...) | KOLD (...) | HND (...) | Price (...)
        
        Args:
            data_dict: {
                'date': '02-02-2026',
                'BOIL': [{'month': 'MAR26', 'val': 123}, {'month': 'APR26', 'val': 456}],
                'HNU': [...],
                ...
                'Price': [{'month': 'MAR26', 'val': 3.12}, ...]
            }
        """
        if not self.service:
            logger.error("No Service available")
            return

        range_name = 'Daily Holdings (NG ETFs)!A:AC' 
        
        # Order of groups based on Excel analysis
        groups = ['BOIL', 'HNU', 'UNG', 'KOLD', 'HND', 'Price']
        
        row = [data_dict.get('date', '')]
        
        for group in groups:
            holdings = data_dict.get(group, [])
            # We need top 2 holdings (C1, C2)
            # If holdings are missing, fill with empty
            
            # C1
            if len(holdings) > 0:
                row.append(holdings[0].get('month', ''))
                row.append(holdings[0].get('val', ''))
            else:
                row.extend(['', ''])
                
            # C2
            if len(holdings) > 1:
                row.append(holdings[1].get('month', ''))
                row.append(holdings[1].get('val', ''))
            else:
                row.extend(['', ''])
        
        body = {
            'values': [row]
        }

        try:
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            logger.info(f"{result.get('updates').get('updatedCells')} cells appended.")
        except Exception as e:
            logger.error(f"Error writing to sheet: {e}")

if __name__ == "__main__":
    # Test
    # SHEET_ID must be set
    sheet_id = os.environ.get("SHEET_ID", "PLACEHOLDER_ID")
    sm = SheetManager(sheet_id)
    # sm.append_data({'date': '01-01-2026', 'BOIL': 100})
