
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

    def _find_row_for_date(self, date_str):
        """
        Search for a row with the given date in column A.
        Returns row number (1-indexed) if found, None otherwise.
        """
        if not self.service:
            return None
        
        try:
            range_name = 'Daily Holdings (NG ETFs)!A:A'
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            # Search for matching date (skip header row at index 0)
            for i, row in enumerate(values):
                if i == 0:  # Skip header
                    continue
                if row and len(row) > 0 and row[0] == date_str:
                    return i + 1  # Return 1-indexed row number
            
            return None
        except Exception as e:
            logger.warning(f"Error searching for date: {e}")
            return None

    def append_data(self, data_dict):
        """
        Add or update a row in 'Daily Holdings (NG ETFs)'.
        If date exists, updates that row. If new date, appends new row.
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

        date_str = data_dict.get('date', '')
        
        # Check if row for this date already exists
        existing_row_num = self._find_row_for_date(date_str)
        
        # Order of groups based on Excel analysis
        groups = ['BOIL', 'HNU', 'UNG', 'KOLD', 'HND', 'Price']
        
        row = [date_str]
        
        for group in groups:
            holdings = data_dict.get(group, [])
            # We need top 2 holdings (C1, C2)
            # If holdings are missing, fill with empty
            
            # C1
            if len(holdings) > 0:
                row.append("'" + str(holdings[0].get('month', '')))
                # Handle cases where value might be very large or formatted weirdly
                val = holdings[0].get('val', '')
                row.append(val)
            else:
                row.extend(['', ''])
                
            # C2
            if len(holdings) > 1:
                row.append("'" + str(holdings[1].get('month', '')))
                val = holdings[1].get('val', '')
                row.append(val)
            else:
                row.extend(['', ''])
        
        body = {
            'values': [row]
        }

        try:
            if existing_row_num:
                # Update existing row
                range_name = f'Daily Holdings (NG ETFs)!A{existing_row_num}:AC{existing_row_num}'
                result = self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                logger.info(f"Updated row {existing_row_num} for date {date_str}. {result.get('updatedCells')} cells updated.")
            else:
                # Append new row
                range_name = 'Daily Holdings (NG ETFs)!A:AC'
                result = self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                logger.info(f"Appended new row for date {date_str}. {result.get('updates').get('updatedCells')} cells appended.")
            
            # Enforce Number Formatting on Value Columns
            self._update_formatting()
            
        except Exception as e:
            logger.error(f"Error writing to sheet: {e}")

    def _update_formatting(self):
        """
        Force 'Number' format on Value columns to prevent Date auto-conversion.
        Also Apply BOLD and Date Format to the Date Column (A).
        """
        if not self.service: return
        
        target_sheet_title = 'Daily Holdings (NG ETFs)'
        sheet_id = None
        
        # Try to find sheetId by Name
        try:
            meta = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = meta.get('sheets', [])
            
            for s in sheets:
                title = s['properties']['title']
                sid = s['properties']['sheetId']
                if title == target_sheet_title:
                    sheet_id = sid
                    break
            
            if sheet_id is None:
                if len(sheets) > 0:
                    sheet_id = sheets[0]['properties']['sheetId']
                else:
                    return

        except Exception as e:
            logger.error(f"Failed to fetch sheet metadata: {e}")
            return

        requests = []
        
        # 1. Format Date Column (A / Index 0) -> BOLD + Date Format (M/d/yyyy) + LEFT alignment
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startColumnIndex": 0,
                    "endColumnIndex": 1,
                    "startRowIndex": 1 
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type": "DATE",
                            "pattern": "M/d/yyyy"
                        },
                        "textFormat": {
                            "bold": True
                        },
                        "horizontalAlignment": "LEFT"
                    }
                },
                "fields": "userEnteredFormat(numberFormat,textFormat,horizontalAlignment)"
            }
        })

        # 2. Format Value Columns -> Number with decimals (for prices)
        # Columns: 2,4,6,8,10,12,14,16,18,20,22,24
        for col_idx in range(2, 26, 2):
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1,
                        "startRowIndex": 1 
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": "NUMBER",
                                "pattern": "#,##0.0000" 
                            },
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat(numberFormat,horizontalAlignment)"
                }
            })
        
        # 3. Format Month Columns -> Text with LEFT alignment
        # Columns: 1,3,5,7,9,11,13,15,17,19,21,23,25
        for col_idx in range(1, 26, 2):
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1,
                        "startRowIndex": 1 
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat.horizontalAlignment"
                }
            })
            
        body = { "requests": requests }
        try:
            resp = self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            logger.info(f"Updated formatting. Response: {len(resp.get('replies'))} replies")
        except Exception as e:
            logger.warning(f"Failed to update formatting: {e}")

if __name__ == "__main__":
    # Test
    # SHEET_ID must be set
    sheet_id = os.environ.get("SHEET_ID", "PLACEHOLDER_ID")
    sm = SheetManager(sheet_id)
    # sm.append_data({'date': '01-01-2026', 'BOIL': 100})
