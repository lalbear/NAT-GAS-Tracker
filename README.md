
# Natural Gas ETF Tracker

Automated tracker for "Net Contract Exposure" of Natural Gas ETFs (BOIL, KOLD, UNG, HNU, HND).

## Features
- **Scraping**: Collects data from ProShares, BetaPro, and USCF websites using Selenium.
- **Calculation**: Computes daily contract equivalents based on AUM/NAV/Swaps logic.
- **Data Storage**: Appends daily results to a Google Sheet.
- **Automation**: GitHub Actions workflow runs every day at 10:00 AM/PM UTC.

## Setup

### 1. Prerequisites
- Python 3.9+
- Chrome/ChromeDriver (managed automatically)
- Google Cloud Platform Service Account Key

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Google Sheets Setup
1. Share your Google Sheet with the Service Account email.
2. Note the `Spreadsheet ID` (from the URL).
3. Ensure the sheet has a tab named **'Daily Holdings (NG ETFs)'**.

### 4. Running Locally
Set environment variables and run:
```bash
export SHEET_ID="your_spreadsheet_id"
export GCP_SA_KEY='{"type": "service_account", ...}'  # OR put credentials.json in root

python src/main.py
```

### 5. Deployment (GitHub Actions)
1. Go to your GitHub Repo -> **Settings** -> **Secrets and variables** -> **Actions**.
2. Add Repository Secrets:
   - `GCP_SA_KEY`: The content of your Service Account JSON key (minified).
   - `SHEET_ID`: The ID of your Google Sheet.
3. The workflow will run automatically on the defined schedule.

## FAQ

### Can I use my existing Excel file?
**Yes.** 
1. Upload your `.xlsx` file (e.g., `Copy of Nat Gas ETFs...`) to Google Drive.
2. Open it as a Google Sheet.
3. Use its **ID** for the `SHEET_ID` secret.
4. Share it with the Service Account email.

The script is configured to match the columns **exactly** as they are in your Excel file (`Date | BOIL C1/C2 | ...`), so it will append new data correctly.
