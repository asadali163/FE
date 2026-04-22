import requests
import pandas as pd

# -----------------------------
# Config
# -----------------------------
BASE_URL = "https://openholidaysapi.org"

PARAMS_PUBLIC = {
    "countryIsoCode": "FR",
    "validFrom": "2026-01-01",
    "validTo": "2026-04-30",
}

PARAMS_SCHOOL = {
    "countryIsoCode": "FR",
    "subdivisionCode": "FR-ZB",  # Paris region
    "languageIsoCode": "EN",
    "validFrom": "2026-01-01",
    "validTo": "2026-04-30",
}


# -----------------------------
# Helper function
# -----------------------------
def extract_name(name_list, lang="EN"):
    """Extract holiday name for a given language"""
    for item in name_list:
        if item["language"] == lang:
            return item["text"]
    return name_list[0]["text"] if name_list else None


def fetch_data(endpoint, params, holiday_type):
    """Fetch and normalize API data"""
    url = f"{BASE_URL}/{endpoint}"
    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()

    records = []
    for h in data:
        record = {
            "id": h.get("id"),
            "name": extract_name(h.get("name", [])),
            "start_date": h.get("startDate"),
            "end_date": h.get("endDate"),
            "type": h.get("type"),
            "holiday_category": holiday_type,  # Public or School
            "regional_scope": h.get("regionalScope"),
            "temporal_scope": h.get("temporalScope"),
            "nationwide": h.get("nationwide", None),
        }
        records.append(record)

    return pd.DataFrame(records)


# -----------------------------
# Fetch Data
# -----------------------------
df_public = fetch_data("PublicHolidays", PARAMS_PUBLIC, "Public")
df_school = fetch_data("SchoolHolidays", PARAMS_SCHOOL, "School")

# -----------------------------
# Combine
# -----------------------------
df_all = pd.concat([df_public, df_school], ignore_index=True)

# Convert to datetime (important for your time-series work)
df_all["start_date"] = pd.to_datetime(df_all["start_date"])
df_all["end_date"] = pd.to_datetime(df_all["end_date"])

# Sort
df_all = df_all.sort_values("start_date")

# -----------------------------
# Save to CSV
# -----------------------------
df_all.to_csv("./data/France/processed_data/holidays.csv", index=False)

print("✅ File saved: france_holidays_2026_jan_apr.csv", df_all.shape)
print(df_all.head)
