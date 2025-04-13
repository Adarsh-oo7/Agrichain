import pandas as pd
from prophet import Prophet
df = pd.DataFrame({
    "ds": pd.date_range("2020-01-01", "2024-12-01", freq="MS"),
    "y": [3000 + i * 10 for i in range(60)]  # Linear trend
})
model = Prophet(yearly_seasonality=5, changepoint_prior_scale=0.01)
model.fit(df, algorithm="LBFGS")
future = model.make_future_dataframe(periods=3, freq="MS")
forecast = model.predict(future)
print(forecast[["ds", "yhat"]].tail(3))