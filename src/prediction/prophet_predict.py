import pandas as pd
import numpy as np
from prophet import Prophet
from itertools import product

from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
)

import matplotlib.pyplot as plt


class ProphetPredict:
    def __init__(self):
        self.param_grid = {
            "changepoint_prior_scale": [0.01, 0.1, 0.5],
            "seasonality_prior_scale": [1.0, 5.0, 10.0],
            "seasonality_mode": ["additive", "multiplicative"],
        }

        self.all_params = [
            dict(zip(self.param_grid.keys(), v))
            for v in product(*self.param_grid.values())
        ]

    # -------------------------------
    # Train helper
    # -------------------------------
    def _train(self, df_train, params):
        model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=params["changepoint_prior_scale"],
            seasonality_prior_scale=params["seasonality_prior_scale"],
            seasonality_mode=params["seasonality_mode"],
        )
        model.fit(df_train)
        return model

    # -------------------------------
    # Evaluate helper
    # -------------------------------
    def _evaluate(self, forecast, df_test):
        forecast_test = forecast[forecast["ds"].isin(df_test["ds"])]

        eval_df = df_test.merge(
            forecast_test[["ds", "yhat"]],
            on="ds",
            how="left",
        )

        mae = mean_absolute_error(eval_df["y"], eval_df["yhat"])
        mape = mean_absolute_percentage_error(eval_df["y"], eval_df["yhat"])
        rmse = np.sqrt(mean_squared_error(eval_df["y"], eval_df["yhat"]))

        return {"MAE": mae, "MAPE": mape, "RMSE": rmse}, eval_df

    # -------------------------------
    # MAIN PREDICT FUNCTION
    # -------------------------------
    def predict(self, data: pd.Series, days_ahead: int) -> pd.Series:

        # Step 1: format data
        df = data.reset_index()
        df.columns = ["ds", "y"]
        df = df.sort_values("ds")

        # Take last 7 days for testing.
        df_train = df.iloc[:-7]
        df_test = df.iloc[-7:]
        # # Step 2: train-test split
        # split_idx = int(len(df) * 0.8)
        # df_train = df.iloc[:split_idx]
        # df_test = df.iloc[split_idx:]

        best_score = float("inf")
        best_model = None
        best_params = None

        # Step 3: grid search
        for params in self.all_params:
            model = self._train(df_train, params)

            future = model.make_future_dataframe(periods=len(df_test), freq="D")
            forecast = model.predict(future)

            result, _ = self._evaluate(forecast, df_test)

            if result["MAE"] < best_score:
                best_score = result["RMSE"]
                best_model = model
                best_params = params

        # Step 4: retrain on full dataset

        print(f"Best params: {best_params}, best score: {best_score}")

        final_model = self._train(df, best_params)

        # Step 5: future forecast
        future = final_model.make_future_dataframe(periods=days_ahead, freq="D")
        forecast = final_model.predict(future)

        forecast_future = forecast.tail(days_ahead)

        # Step 6: return only future values
        return pd.Series(
            forecast_future["yhat"].values, index=forecast_future["ds"], name="forecast"
        )


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


def plot_result(y: pd.Series, yhat: pd.Series):
    plt.plot(y, label="Actual", marker="o")
    plt.plot(yhat, label="Predicted", marker="x")
    plt.title("Actual vs Predicted Sales Quantity for Shop")
    plt.xlabel("Date")
    plt.ylabel("Sales Quantity")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    df_path = "/home/asad/Desktop/FE2/data/France/processed_data/combined_df.csv"
    df_sellin, df_sellout = load_data(df_path)

    df_selected_fmc = df_sellout[df_sellout["category"] == "FMC"].copy()

    df_selected = df_selected_fmc[
        (df_selected_fmc["customer_code"] == "0011t000011bAt2AAE")
        & (df_selected_fmc["sku_code"] == "a0U1t000002PXlqEAG")
    ].copy()

    df_selected = df_selected.groupby("date")["sales_quantity"].sum().reset_index()

    df_selected["ds"] = df_selected["date"]
    df_selected["y"] = df_selected["sales_quantity"]

    data = pd.Series(df_selected["y"].values, index=df_selected["ds"], name="y")

    data_train = data[:-7]
    data_test = data[-7:]

    predictor = ProphetPredict()
    result = predictor.predict(data_train, 7)

    # eval_df = {
    #     "y": data_test,
    #     "yhat": result,
    #     "ds": data_test.index,
    # }

    # eval_df = pd.DataFrame(eval_df)

    # plot_results(eval_df)

    print(f"#### TEST DATA: {data_test}")
    print(f"#### PREDICTED DATA: {result}")

    plot_result(data_test, result)
