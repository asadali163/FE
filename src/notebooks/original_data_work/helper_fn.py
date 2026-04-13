import pandas as pd
import re
from pathlib import Path
import numpy as np

def extract_month(filename):
    # Match both short and full month names for Jan, Feb, March
    match = re.search(r'jan(uary)?|feb(ruary)?|mar(ch)?', filename.lower())
    if not match:
        return None
    # Normalize to short form
    month_map = {'jan': 'Jan', 'feb': 'Feb', 'mar': 'March'}
    key = match.group(0)[:3]  # Take first 3 letters
    return month_map.get(key)

def load_sellout_data(base_path):
    base_path = Path(base_path)
    data_dict = {}

    for provider_folder in base_path.iterdir():
        if provider_folder.is_dir():
            provider = provider_folder.name

            for file in provider_folder.glob("*"):
                if file.suffix in [".csv", ".xlsx"]:
                    # Load file
                    if file.suffix == ".csv":
                        df = pd.read_csv(file)
                    else:
                        df = pd.read_excel(file)

                    # Extract month from filename
                    month = extract_month(file.name)

                    key = (provider, month)
                    data_dict[key] = df

    return data_dict

## Column Standardization and Cleaning
def clean_sellin(df, month_label, BASE_COL):
    df = df.copy()
    
    # Determine which column to rename to sku_record
    if 'SKU Record' in df.columns:
        sku_col = 'SKU Record'
    elif 'Record Type' in df.columns:
        sku_col = 'Record Type'
    else:
        sku_col = None  # No column exists

    # Prepare rename mapping
    rename_map = {
        BASE_COL: 'base_unit',
        'SALES UNIT (outer)': 'outer_unit',
        'Point of sales code (Logista)': 'pos_code',
        'Outlet SF ID': 'outlet_sf_id',
        'SKU code (Logista)': 'sku_code',
        'Trade SKU SF ID': 'sku_sf_id',
        'Delivery Date': 'delivery_date_raw',
        'Sales Date': 'sales_date_raw',
    }
    if sku_col is not None:
        rename_map[sku_col] = 'sku_record'

    # Rename columns
    df.rename(columns=rename_map, inplace=True)

    # Convert dates
    df['date']          = pd.to_datetime(df['sales_date_raw'].astype(str), format='%Y%m%d')
    df['delivery_date'] = pd.to_datetime(df['delivery_date_raw'].astype(str), format='%Y%m%d')
    df['delivery_lag']  = (df['delivery_date'] - df['date']).dt.days

    # Additional columns
    df['month'] = month_label
    df['dow']   = df['date'].dt.day_name()
    df['week']  = df['date'].dt.isocalendar().week.astype(int)
    df['day']   = df['date'].dt.day

    # Sentinel 0 → NaN for optional columns
    if 'sku_sf_id' in df.columns:
        df['sku_sf_id'] = df['sku_sf_id'].replace(0, np.nan)
    if 'sku_record' in df.columns:
        df['sku_record'] = df['sku_record'].replace(0, np.nan)

    return df



