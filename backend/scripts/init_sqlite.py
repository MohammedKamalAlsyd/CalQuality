# python -m scripts.init_sqlite

import sqlite3
import pandas as pd
import os

# Paths
EXCEL_PATH = 'data/excel/ParcelPilot_Assessment_Data.xlsx'
DB_PATH = 'data/parcelpilot.db'

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    print(f"Reading Excel file from {EXCEL_PATH}...")
    
    # Read sheets into a dictionary of dataframes
    try:
        xls = pd.read_excel(EXCEL_PATH, sheet_name=None)
    except FileNotFoundError:
        print(f"Error: Could not find {EXCEL_PATH}. Please ensure the file is there.")
        return

    # Process Accounts, Orders, and Tickets (ignoring 'readme')
    for sheet_name in ['accounts', 'orders', 'tickets']:
        if sheet_name in xls:
            df = xls[sheet_name]
            # Clean column names (strip spaces, lowercase) just in case
            df.columns = [col.strip().lower() for col in df.columns]
            
            # Write to SQLite
            df.to_sql(sheet_name, conn, if_exists='replace', index=False)
            print(f"✅ Successfully loaded '{sheet_name}' table ({len(df)} rows).")
        else:
            print(f"⚠️ Warning: Sheet '{sheet_name}' not found in Excel file.")
            
    print(f"\nDatabase created successfully at {DB_PATH}")
    conn.close()

if __name__ == "__main__":
    init_db()