
import pandas as pd
import os

file_path = '/Users/pranjalupadhyay/Desktop/projects/ETF_Tracker/Copy of Nat Gas ETFs Contracts Holdings .xlsx'

try:
    # Read all sheet names
    xl = pd.ExcelFile(file_path)
    print(f"Sheet names: {xl.sheet_names}")

    # Read the first few rows of the main sheet (assuming first or named 'Daily Holdings' or similar)
    # The prompt mentions "Daily Holdings"
    target_sheet = 'Daily Holdings' if 'Daily Holdings' in xl.sheet_names else xl.sheet_names[0]
    
    df = xl.parse(target_sheet, nrows=5)
    print(f"\n--- Top 5 rows of '{target_sheet}' ---")
    print(df.to_string())
    
    print("\n--- Columns ---")
    print(list(df.columns))

except Exception as e:
    print(f"Error reading excel: {e}")
