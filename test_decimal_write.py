#!/usr/bin/env python3
"""
Test script to verify decimal precision is preserved in Google Sheets.
This will write a test row with decimal prices to confirm formatting works.
"""

import os
import sys
sys.path.insert(0, 'src')

from sheets import SheetManager
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_decimal_write():
    """Write test data with decimal prices to verify formatting."""
    
    # Check for credentials file
    if os.path.exists("key.json"):
        logger.info("Found key.json for authentication")
        # Rename to credentials.json temporarily for SheetManager
        import shutil
        if not os.path.exists("credentials.json"):
            shutil.copy("key.json", "credentials.json")
    elif not os.path.exists("credentials.json"):
        logger.error("No credentials file found (key.json or credentials.json)")
        return
    
    # Get sheet ID from environment or prompt
    sheet_id = os.environ.get("SHEET_ID")
    
    if not sheet_id:
        print("\nSHEET_ID not set in environment.")
        print("Please enter your Google Sheet ID (found in the URL):")
        print("Example: https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit")
        sheet_id = input("Sheet ID: ").strip()
        
        if not sheet_id:
            logger.error("Sheet ID is required")
            return
    
    logger.info(f"Using Sheet ID: {sheet_id[:10]}...")
    
    # Initialize Sheet Manager
    sm = SheetManager(sheet_id)
    
    if not sm.service:
        logger.error("Failed to authenticate with Google Sheets")
        return
    
    # Create test data with decimal prices
    test_data = {
        'date': '2/15/2026',  # Today's date (test row)
        'BOIL': [
            {'month': 'MAR26', 'val': 1000},
            {'month': 'APR26', 'val': 500}
        ],
        'Price': [
            {'month': 'APR26', 'val': 3.104},  # This should show as 3.1040
            {'month': 'MAY26', 'val': 3.117}   # This should show as 3.1170
        ]
    }
    
    logger.info("Writing test data to sheet...")
    logger.info(f"Price data: {test_data['Price']}")
    
    # Write to sheet
    sm.append_data(test_data)
    
    logger.info("✅ Test data written! Check your sheet to verify prices show as 3.1040 and 3.1170")
    logger.info("If you see 3.0000 or 3 instead, there's still an issue.")
    logger.info("Otherwise, the decimal formatting is working correctly!")

if __name__ == "__main__":
    test_decimal_write()
