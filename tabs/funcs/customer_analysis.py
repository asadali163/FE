import pandas as pd
import plotly.graph_objects as go


# def detect_spikes_global(df, threshold):
#     df = df.copy()

#     mean = df["sales_quantity"].mean()
#     std = df["sales_quantity"].std()

#     df["z_score"] = (df["sales_quantity"] - mean) / std
#     df["is_spike"] = df["z_score"] > threshold  # threshold adjustable

#     return df


def detect_spikes_global(df, threshold):
    df = df.copy()

    # Ensure datetime index or column for weekday extraction
    df["weekday"] = pd.to_datetime(df["date"]).dt.dayofweek  # 0=Mon, 6=Sun

    # Compute per-weekday mean and std
    weekday_stats = df.groupby("weekday")["sales_quantity"].agg(["mean", "std"])

    # Map stats back to each row
    df["weekday_mean"] = df["weekday"].map(weekday_stats["mean"])
    df["weekday_std"] = df["weekday"].map(weekday_stats["std"])

    # Weekday-aware z-score
    df["z_score"] = (df["sales_quantity"] - df["weekday_mean"]) / df["weekday_std"]
    df["is_spike"] = df["z_score"] > threshold

    return df


def add_event_data(df_selected, df_events):
    df = df_selected.copy()
    events = df_events.copy()

    # Collapse multiple events per day → unique event days
    event_dates = set(events["date"].dt.date)
    event_dates = set(pd.to_datetime(list(event_dates)))

    # Create helper
    def has_event(d):
        return d in event_dates

    # Add features
    df["event_same_day"] = df["date"].apply(has_event)
    df["event_day_before"] = df["date"].apply(
        lambda d: (d - pd.Timedelta(days=1)) in event_dates
    )
    df["event_day_after"] = df["date"].apply(
        lambda d: (d + pd.Timedelta(days=1)) in event_dates
    )

    return df


def process_customer(df_sellout, df_events, threshold):

    # --- sales aggregation ---
    df_selected = df_sellout.groupby(["date", "customer_code"], as_index=False).agg(
        {"sales_quantity": "sum"}
    )

    df_selected = detect_spikes_global(df_selected, threshold)

    # --- metadata ---
    metadata_cols = [
        "customer_code",
        "customer_name",
        "latitude",
        "longitude",
        "route",
        "brand",
        "channel_name",
    ]

    df_meta = df_sellout[metadata_cols].drop_duplicates(subset=["customer_code"])
    df_selected = df_selected.merge(df_meta, on="customer_code", how="left")

    df_selected["latitude"] = df_selected["latitude"].round(4)
    df_selected["longitude"] = df_selected["longitude"].round(4)

    # --- event filtering (FIXED) ---
    df_event_selected = df_events.merge(
        df_selected[["latitude", "longitude"]].drop_duplicates(),
        left_on=["shop_lat", "shop_lon"],
        right_on=["latitude", "longitude"],
        how="inner",
    )

    df_event_selected = df_event_selected.drop(columns=["latitude", "longitude"])

    # --- add event features ---
    df_selected = add_event_data(df_selected, df_event_selected)

    return df_selected


def plot_customer(df_selected: pd.DataFrame, df_selected_sellin: pd.DataFrame):
    print(f"DF shape: {df_selected.shape}")
    fig = go.Figure()

    # -----------------------
    # 1. Main sales line
    # -----------------------
    fig.add_trace(
        go.Scatter(
            x=df_selected["date"],
            y=df_selected["sales_quantity"],
            mode="lines+markers",
            name="Sales",
            line=dict(color="steelblue"),
            marker=dict(size=4),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_selected_sellin["date"],
            y=df_selected_sellin["sales_quantity"],
            mode="lines+markers",
            name="Sell-In",
            line=dict(color="green"),
            marker=dict(size=4),
        )
    )

    # -----------------------
    # 2. Spikes only
    # -----------------------
    spikes = df_selected[df_selected["is_spike"]].copy()

    fig.add_trace(
        go.Scatter(
            x=spikes["date"],
            y=spikes["sales_quantity"],
            mode="markers",
            name="Spikes",
            marker=dict(size=10, color="red", symbol="circle"),
            # 🔥 event context attached here
            customdata=spikes[
                ["event_same_day", "event_day_before", "event_day_after"]
            ],
            # hovertemplate=(
            #     "<b>Spike Point</b><br>"
            #     "Date: %{x}<br>"
            #     "Sales: %{y}<br><br>"
            #     "Event Same Day: %{customdata[0]}<br>"
            #     "Event Day Before: %{customdata[1]}<br>"
            #     "Event Day After: %{customdata[2]}<br>"
            #     "<extra></extra>"
            # ),
        )
    )

    fig.update_layout(
        title="Daily Sales with Spikes & Event Context",
        xaxis_title="Date",
        yaxis_title="Sales Quantity",
        template="plotly_white",
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig
