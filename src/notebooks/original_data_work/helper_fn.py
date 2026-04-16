import pandas as pd
import re
from pathlib import Path
import numpy as np
from prophet import Prophet

from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
)

import matplotlib.pyplot as plt


def extract_month(filename):
    # Match both short and full month names for Jan, Feb, March
    match = re.search(r"jan(uary)?|feb(ruary)?|mar(ch)?", filename.lower())
    if not match:
        return None
    # Normalize to short form
    month_map = {"jan": "Jan", "feb": "Feb", "mar": "March"}
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
    if "SKU Record" in df.columns:
        sku_col = "SKU Record"
    elif "Record Type" in df.columns:
        sku_col = "Record Type"
    else:
        sku_col = None  # No column exists

    # Prepare rename mapping
    rename_map = {
        BASE_COL: "base_unit",
        "SALES UNIT (outer)": "outer_unit",
        "Point of sales code (Logista)": "pos_code",
        "Outlet SF ID": "outlet_sf_id",
        "SKU code (Logista)": "sku_code",
        "Trade SKU SF ID": "sku_sf_id",
        "Delivery Date": "delivery_date_raw",
        "Sales Date": "sales_date_raw",
    }
    if sku_col is not None:
        rename_map[sku_col] = "sku_record"

    # Rename columns
    df.rename(columns=rename_map, inplace=True)

    # Convert dates
    df["date"] = pd.to_datetime(df["sales_date_raw"].astype(str), format="%Y%m%d")
    df["delivery_date"] = pd.to_datetime(
        df["delivery_date_raw"].astype(str), format="%Y%m%d"
    )
    df["delivery_lag"] = (df["delivery_date"] - df["date"]).dt.days

    # Additional columns
    df["month"] = month_label
    df["dow"] = df["date"].dt.day_name()
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["day"] = df["date"].dt.day

    # Sentinel 0 → NaN for optional columns
    if "sku_sf_id" in df.columns:
        df["sku_sf_id"] = df["sku_sf_id"].replace(0, np.nan)
    if "sku_record" in df.columns:
        df["sku_record"] = df["sku_record"].replace(0, np.nan)

    return df


def load_data(df_path):
    df = pd.read_csv(df_path, low_memory=False)

    df.rename(
        columns={
            "Sales Date": "date",
            "Outlet SF ID": "customer_code",
            "Store Participant Code": "customer_name",
            "SKU SF ID": "sku_code",
            "SKU Name": "sku_name",
            "Brand Variant": "brand_variant",
            "Brand Family": "brand_name",
            "Category": "category",
            "Volume in Unit": "sales_amount",
            "Volume in Packs": "sales_quantity",
            "Ownership Type": "channel_name",
            "Latitude": "latitude",
            "Longitude": "longitude",
            "Territory Id": "route",
            "Brand": "brand",
            "SKU Clean": "sku_clean",
            "Month": "month",
        },
        inplace=True,
    )

    df["date"] = pd.to_datetime(df["date"])

    df_sellin = df[df["data_type"] == "sell_in"].copy()
    df_sellout = df[df["data_type"] == "sell_out"].copy()

    return df_sellin, df_sellout


def get_fmc_category_only(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["category"] == "FMC"].copy()


def give_monthly_sales_data(sellout, include_empty_sku=True):

    df = sellout[sellout["category"] == "FMC"].copy()

    # print(df.shape)

    if not include_empty_sku:
        df = df[df["sku_code"] != "0"]

    # print(df.shape)

    # Extract month (optional: keep year too if multi-year data)
    df["year_month"] = df["date"].dt.to_period("M")

    # Aggregate sales
    df_monthly = df.groupby("year_month")["sales_quantity"].sum().reset_index()

    # Convert to timestamp (nice for plotting)
    df_monthly["year_month"] = df_monthly["year_month"].dt.to_timestamp()

    return df_monthly


def give_monthly_sales_data_customer_level(
    sellout, customer_code, include_empty_sku=True
):

    df = sellout[sellout["category"] == "FMC"].copy()

    if not include_empty_sku:
        df = df[df["sku_code"] != "0"]

    df = df[df["customer_code"] == customer_code].copy()

    # Extract month (optional: keep year too if multi-year data)
    df["year_month"] = df["date"].dt.to_period("M")

    # Aggregate sales
    df_monthly = df.groupby("year_month")["sales_quantity"].sum().reset_index()

    # Convert to timestamp (nice for plotting)
    df_monthly["year_month"] = df_monthly["year_month"].dt.to_timestamp()

    return df_monthly


def evaluate(forecast, df_test):
    forecast_test = forecast[forecast["ds"].isin(df_test["ds"])]
    eval_df = df_test.merge(forecast_test[["ds", "yhat"]], on="ds", how="left")

    mae = mean_absolute_error(eval_df["y"], eval_df["yhat"])
    mape = mean_absolute_percentage_error(eval_df["y"], eval_df["yhat"])
    rmse = np.sqrt(mean_squared_error(eval_df["y"], eval_df["yhat"]))

    return {"MAE": mae, "MAPE": mape, "RMSE": rmse}, eval_df


def train_prophet_with_params(df_train, params, add_holidays=False):
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        changepoint_prior_scale=params["changepoint_prior_scale"],
        seasonality_prior_scale=params["seasonality_prior_scale"],
        seasonality_mode=params["seasonality_mode"],
    )

    if add_holidays:
        model.add_country_holidays(country_name="FR")  # Add country-specific holidays

    model.fit(df_train)
    return model


def plot_results(eval_df):
    plt.figure(figsize=(12, 6))
    plt.plot(eval_df["ds"], eval_df["y"], label="Actual", marker="o")
    plt.plot(eval_df["ds"], eval_df["yhat"], label="Predicted", marker="x")
    plt.title(f"Actual vs Predicted Sales Quantity for Shop")
    plt.xlabel("Date")
    plt.ylabel("Sales Quantity")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()
