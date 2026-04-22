import os
import pandas as pd


# File paths

MASTER_OUTLETS = "data/raw/account_sku_master/FR_Outlets Extract_Paris.xlsx"
MASTER_SKUS = "data/raw/account_sku_master/FR_SKU Extract.xlsx"

SELL_IN_FILES = {
    "Jan": "data/raw/sell_in/Logista_Paris_Jan Sell In.xlsx",
    "Feb": "data/raw/sell_in/Logista_Paris_Sell In_Feb.xlsx",
    "Mar": "data/raw/sell_in/Logista_Paris_Sell In_Mar.xlsx",
}

SELL_OUT_FILES = {
    "Bimedia_Jan": "data/raw/sell_out/Bimedia/Bimedia_Sell Out_Jan.xlsx",
    "Bimedia_Feb": "data/raw/sell_out/Bimedia/Bimedia_Sell Out_Feb.xlsx",
    "Bimedia_Mar": "data/raw/sell_out/Bimedia/Bimedia_Sell Out_March.xlsx",
    "Devlyx_Jan": "data/raw/sell_out/Devlyx/Devlyx_Sell Out_Jan.csv",
    "Devlyx_Feb": "data/raw/sell_out/Devlyx/Devlyx_Sell Out_Feb.xlsx",
    "Devlyx_Mar": "data/raw/sell_out/Devlyx/Devlyx_Sell Out_March.csv",
    "Logista_Jan": "data/raw/sell_out/Logista/Logista_Sell Out_Jan.xlsx",
    "Logista_Feb": "data/raw/sell_out/Logista/Logista_Sell Out_Feb.xlsx",
    "Logista_Mar": "data/raw/sell_out/Logista/Logista_Sell Out March.csv",
}

SI_VOL_COL = "BASE UNIT\nSticks for Cigarette/Cigars\nGrams for FC\nPacks for NGP"


def _read(path):
    if path.endswith(".csv"):
        return pd.read_csv(path, on_bad_lines="skip")
    return pd.read_excel(path)


def _fix_outlet_ids(dfs, official_ids):
    pos_to_outlet = {}
    for df in dfs:
        if df["month"].iloc[0] != "Jan":
            continue
        official = df[df["Outlet SF ID"].isin(official_ids)]
        mapping = official.drop_duplicates("POS").set_index("POS")["Outlet SF ID"]
        pos_to_outlet.update(mapping.to_dict())

    for df in dfs:
        broken = ~df["Outlet SF ID"].isin(official_ids) & df["POS"].isin(pos_to_outlet)
        if broken.any():
            df.loc[broken, "Outlet SF ID"] = df.loc[broken, "POS"].map(pos_to_outlet)
            print(
                f"  Fixed {df['provider'].iloc[0]} {df['month'].iloc[0]}: "
                f"{broken.sum():,} rows remapped via POS"
            )

    return dfs


def load_all():
    """
    Returns:
        dict with keys:
        - outlets          : official outlet master (958 rows)
        - skus             : official SKU master
        - sell_in          : sell-in, real SKUs only, official outlets
        - sell_out         : sell-out, real SKUs only, official outlets
        - sell_out_market  : sell-out SKU 99999 (total market per outlet)
    """
    outlets = pd.read_excel(MASTER_OUTLETS)
    skus = pd.read_excel(MASTER_SKUS)
    official_ids = set(outlets["Outlet Salesforce Id"].dropna())

    # Load sell-out
    so_dfs = []
    for name, path in SELL_OUT_FILES.items():
        if not os.path.exists(path):
            continue
        df = _read(path)
        provider, month = name.split("_")
        df["provider"] = provider
        df["month"] = month
        so_dfs.append(df)

    so_dfs = _fix_outlet_ids(so_dfs, official_ids)
    sell_out_all = pd.concat(so_dfs, ignore_index=True)
    sell_out_all = sell_out_all[sell_out_all["Outlet SF ID"].isin(official_ids)]

    sell_out = sell_out_all[sell_out_all["SKU"] != 99999].copy()
    sell_out_market = sell_out_all[sell_out_all["SKU"] == 99999].copy()

    # Load sell-in
    si_dfs = []
    for month, path in SELL_IN_FILES.items():
        if not os.path.exists(path):
            continue
        df = _read(path)
        df["month"] = month
        si_dfs.append(df)

    sell_in = pd.concat(si_dfs, ignore_index=True)
    sell_in = sell_in[
        sell_in["Outlet SF ID"].isin(official_ids)
        & (sell_in["SKU code (Logista)"] != 99999)
    ].copy()

    print(
        f"Outlets: {len(official_ids)} | "
        f"Sell-out: {len(sell_out):,} | "
        f"Market (99999): {len(sell_out_market):,} | "
        f"Sell-in: {len(sell_in):,}"
    )

    return {
        "outlets": outlets,
        "skus": skus,
        "sell_in": sell_in,
        "sell_out": sell_out,
        "sell_out_market": sell_out_market,
    }


if __name__ == "__main__":
    data = load_all()
    # Save sellout Data.
    data["sell_out"].to_csv("sellout_data_sir_rizwan.csv", index=False)
    for key, val in data.items():
        print(f"  {key}: {len(val):,} rows x {val.shape[1]} cols")
