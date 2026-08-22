# TourSafe Analytics Demand Forecasting & Uncertainty Intervals

## 1. Statistical Forecasting Methodology

TourSafe incorporates baseline statistical forecasting models to assist emergency response coordinators in staffing and capacity planning without making unwarranted deterministic claims.

### Horizons Supported
1. `next_hour`: Short-term operational readiness (15-minute intervals).
2. `next_day`: Shift planning and daily resource allocation (1-hour intervals).
3. `next_week`: Weekly rotation and zone deployment scheduling (1-day intervals).

---

## 2. Uncertainty Intervals & Prediction Confidence

Every forecast point produces:
- **Predicted Value** (`predicted_value`): Expected demand level based on moving average and temporal cyclic baseline.
- **80% Prediction Interval** (`[lower_bound_p10, upper_bound_p90]`):
  $$\text{Interval} = \hat{y} \pm 1.28 \cdot \sigma_{\text{residual}}$$
- **Confidence Level**: Explicitly labeled at `0.80` (80% confidence).

---

## 3. Strict Insufficient-Data Handling

When fewer than 5 historical data points exist for the requested metric and jurisdiction:
- The service returns status `INSUFFICIENT_DATA`.
- `forecast_points` array is empty.
- An explanatory user-facing message is provided indicating minimum data history requirements.
- No arbitrary synthetic numbers or fake curves are ever returned to authority personnel.
