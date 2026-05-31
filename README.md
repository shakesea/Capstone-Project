# G Coffee Shop Transaction Analysis — Capstone Project

End-to-end data pipeline analyzing transaction data from the **G Coffee** chain in Malaysia (Kuala Lumpur, Selangor, Putrajaya) from **July 2023 to June 2025**. The pipeline encompasses data ingestion, validation, cleaning, integration, feature engineering, exploratory analysis, and forecasting — producing datasets ready for RFM segmentation, market basket analysis (Apriori), supervised learning (XGBoost), and hybrid time-series forecasting.

---

## 1. Project Overview

| Aspect | Description |
|--------|-------------|
| **Objective** | Clean, integrate, and engineer features from 7 raw CSV tables into master datasets for customer segmentation, basket analysis, and transaction forecasting. |
| **Domain** | Retail coffee shop chain — 10 outlets, 8 beverage items, >14.6M transactions. |
| **Data Source** | Kaggle — [G Coffee Shop Transaction 202307 to 202506](https://www.kaggle.com/datasets/geraldooizx/g-coffee-shop-transaction-202307-to-202506) |
| **Time Span** | 1 July 2023 – 30 June 2025 (2 years) |
| **Volume** | ~14.6M transactions, ~29.2M line items, ~2.2M registered users |
| **Currency** | Ringgit Malaysia (RM) — converted in-memory to IDR (1 RM = Rp 3,500) during EDA only. All parquet files store RM. |

---

## 2. Pipeline Architecture

### 2.1 01-LoadData.ipynb — Data Ingestion and Memory Optimisation

- Downloads dataset from Kaggle via `kagglehub.dataset_download()`.
- Reads partitioned CSV files with `glob` + `pd.concat()`:
  - `transactions/*.csv` (14,623,691 rows)
  - `transaction_items/*.csv` (29,246,323 rows)
  - `users/*.csv` (2,196,257 rows)
  - `menu_items.csv`, `stores.csv`, `vouchers.csv`, `payment_methods.csv` (single files).
- **Memory Optimisation** via `function.py`:
  - `optimize_numeric_data()` — downcasts `float64 -> float32`, `int64 -> int8/Int32`.
  - `optimize_object_data()` — converts low-cardinality (<5%) object columns to `category`.
- **Result**: Memory footprint reduced significantly, e.g., Transactions from 2,915 MB to 669 MB.
- **Output**: Intermediate `.parquet` files per table.

### 2.2 02-DataValidation.ipynb — Type Standardisation and Validation

- **Data type standardisation**:
  - `transaction_id` -> `str`
  - `user_id`, `voucher_id` -> `Int64` (nullable)
  - `created_at`, `birthdate`, `registered_at` -> `datetime64`
  - `valid_from`, `valid_to` -> `datetime64`
- **Deep validation** (`run_deep_validation()`):
  - PK duplicates: 0 duplicates found.
  - FK integrity: 0 orphan transactions by `store_id`.
  - Future dates: 0 transactions with `created_at` after today.
  - Age bounds: 0 users with age < 12 or > 100 at registration.
- **Output**: Validated `.parquet` files per table.

### 2.3 03-DataCleaning.ipynb — Data Cleaning

#### a. Invalid Value Inspection
- Orphan transactions (user_id not in Users table): **0 rows**.
- Negative monetary values: **0 rows**.
- Negative item quantity/price: **0 rows**.
- Orphan items (transaction_id not in header): **0 rows**.
- Unregistered menu items: **0 rows**.
- Price consistency: **0 items** with differing `unit_price`.

#### b. Duplicate Handling
- Full duplicates in `df_TransItem`: **802,939 rows**.
- Composite duplicates `(transaction_id, item_id, created_at)`: **4,645,360 rows**.
- Policy: Remove all rows within a `(transaction_id, item_id)` group with time difference <= 30 seconds — **2,360,635 rows removed**.
- Deterministic dedup (Rev): Row with maximum `subtotal` retained.
- **Final**: 0 duplicate rows remaining.

#### c. Header-Detail Reconciliation
- **2,284,725 transactions** had `original_amount` inconsistent with `SUM(subtotal)` of items.
- Correction: `original_amount` overwritten with `SUM(subtotal)`.
- Final: `final_amount = original_amount - discount_applied`.
- Rev: `original_amount_header` backed up as audit trail before overwrite.

#### d. Discount Validation
- Negative discount check: 784 transactions where discount > `original_amount` (caused by SALES50 voucher).
- Capping: `discount_applied = min(discount_applied, original_amount)`. Result: 0 negative transactions.
- Cross-check against voucher rules: 0 mismatches.

#### e. Outlier Treatment
Three methods compared for `final_amount` (initial skewness ~0.53):
| Method | Data Loss | Final Skewness |
|--------|-----------|----------------|
| IQR (1.5xIQR) | 30,633 (0.21%) | 0.50 |
| **Capping (P99)** | **0 (0%)** | **0.49** |
| Z-Score (\|z\|>3) | 30,619 (0.21%) | 0.50 |

**Decision**: Capping at percentile 99 selected — retains 100% of data with best skewness reduction.

#### f. Missing Values
- `available_from` and `available_to` columns in menu_items dropped (100% null).

### 2.4 04-JoinData.ipynb — Table Joining

#### Join Strategy
```
Step 1: df_MasterTrans = df_Trans
    LEFT JOIN df_Users   -> ON user_id
    LEFT JOIN df_stores  -> ON store_id

Step 2: df_Master = df_TransItem
    LEFT JOIN df_menu          -> ON item_id
    LEFT JOIN df_MasterTrans   -> ON transaction_id

Step 3: df_Master
    LEFT JOIN df_payment  -> ON payment_method_id = method_id
```

#### Validation
- Row count: 26,885,688 (matches input).
- Orphan checks: 0 for menu, store, header.
- Financial audit: 14,623,691 transactions balanced (`original_amount = SUM(subtotal)`).
- Column cleanup: Redundant `_x`/`_y` suffix columns removed.

### 2.5 05-FeatureEngineering.ipynb — Feature Engineering

#### a. Temporal Features
| Feature | Derivation |
|---------|-----------|
| `hour` | `dt.hour` (0-23) |
| `month` | `dt.month` (1-12) |
| `day_name` | `dt.day_name()` |
| `month_name` | `dt.month_name()` |
| `is_weekend` | 'Weekend' if Saturday/Sunday, else 'Weekday' |
| `transaction_period` | Morning (5-10), Afternoon (11-15), Evening (16-19), Night (20-23), Late Night (0-4) |

#### b. Categorical Features
| Feature | Derivation |
|---------|-----------|
| `member_status` | 'Member' if `user_id NOT NULL`, else 'Guest' |
| `is_voucher_used` | 'Voucher' if `voucher_id NOT NULL`, else 'No Voucher' |
| `discount_ratio` | `discount_applied / (original_amount + 1e-6)` |

#### c. Transaction Aggregation -> `df_transaction_features`
Group by `transaction_id`:
| Column | Aggregation | New Name |
|--------|-------------|----------|
| `quantity` | SUM | `basket_size` |
| `final_amount` | MAX (deterministic) | -- |
| `discount_applied` | MAX | -- |
| Other fields | MAX | -- |
| `item_id` | COUNT DISTINCT | `item_count` (Rev) |

#### d. RFM Analysis -> `df_rfm`
- Snapshot date: `MAX(created_at) + 1 day` (2025-07-01).
- Scope: Members only (`user_id NOT NULL`).
- Components: Recency (days since last transaction), Frequency (transaction count), Monetary (total spend).
- Scaled RFM (Rev): StandardScaler -> `RFM_Scaled_Recency`, `RFM_Scaled_Frequency`, `RFM_Scaled_Monetary`.

#### e. Apriori Basket Preparation (Rev)
- Binary matrix `transaction_id x item_name` (1 = purchased, 0 = not).
- Filters: remove items with support < 0.1% (none removed); remove single-item baskets (5.6M, 38%); remove baskets > 30 items (none).
- Result: 9,064,669 transactions x 8 items, sparsity 70.6%.
- Output: `df_basket_apriori.parquet`.

#### f. Temporal Train/Test Split (Rev)
- 80/20 temporal split:
  - Training: 11,698,952 transactions (80%) -- 2023-07-01 to 2025-02-04.
  - Test: 2,924,739 transactions (20%) -- 2025-02-04 to 2025-06-30.
- Output: `df_train.parquet`, `df_test.parquet`.

### 2.6 06-EDA.ipynb — Exploratory Data Analysis

#### Business Overview
| Metric | Value (RM) | Value (IDR x Rp3,500) |
|--------|-----------|----------------------|
| Total Revenue | ~RM 444.0 million | ~Rp 1.55 trillion |
| Total Transactions | 14,623,691 | -- |
| Average Transaction Value | ~RM 30.36 | ~Rp 106,260 |
| Member Revenue Share | ~50% | -- |
| Guest Revenue Share | ~50% | -- |

#### Analysis Sections
- **Time-Based**: Daily revenue trend, hourly traffic (peak vs off-peak), monthly revenue, period-based patterns.
- **Customer**: Revenue split (Member vs Guest), ATV comparison, repeat vs one-time behaviour, preference heatmap.
- **Product**: Top 10 menu items by quantity, coffee vs non-coffee revenue, preference by time period and city.
- **Spatial**: Revenue and ATV per city outlet.
- **Payment**: Revenue distribution across cash, card, ewallet methods.
- **Promotion**: Voucher impact on basket size, sensitivity analysis by Member vs Guest.
- **RFM Segmentation (Rev)**: Heuristic quartile-based segments (Champions, Loyal, At Risk, Regular).

### 2.7 06_Modeling_and_Evaluation.ipynb — Forecasting Pipeline (Consolidated)

This notebook supersedes the legacy notebooks `07.ipynb`, `08-Benchmark-Models.ipynb`, `09_Hybrid_Forecast_HW_XGB.ipynb`, and `09-testingXgb.ipynb`. It consolidates all forecasting steps into a single pipeline with four sections:

#### A. Baseline Models (ARIMA, SARIMA, Prophet)
- Univariate time-series models fitted per branch.
- ARIMA/SARIMA with automatic order selection via `auto_arima`.
- Prophet (Facebook) with weekly seasonality.
- Metrics: MAE, RMSE, MAPE per branch, aggregated across all 10 branches.

#### B. XGBoost Supervised Learning
- Pooled multivariate model using autoregressive features (lag_1, lag_7, rolling_avg_7), calendar features (day_of_week, month), voucher_rate, and one-hot encoded city.
- Temporal train/test split at 2025-03-25 (80/20).
- Feature importance analysis (gain-based).
- Residual diagnostics.

#### C. Hybrid Forecasting (Detrending Architectures)
Three architectures compared:
- **HWR-XGB**: Holt-Winters (additive trend, seasonal_periods=365) + XGBoost on residuals.
- **SARIMA-XGB**: SARIMA + XGBoost on residuals.
- **Prophet-XGB**: Prophet + XGBoost on residuals.

XGBoost on residuals uses only non-autoregressive features (day_of_week, month, voucher_rate) to avoid the low-pass filter problem in recursive forecasting.

#### D. Comparative Evaluation and Output
- Cross-architecture comparison on held-out test set.
- Best model selection: lowest MAE on test set.
- 90-day ahead forecast saved as `df_forecast_90days.parquet` for the Voucher Engine.
- Forecast variability check (min, max, std, range per branch).

---

## 3. Custom Module (`function.py`)

### 3.1 Class `CleaningData`
| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `Duplicate(column_name)` | Column name | int | Counts duplicate rows in a column. |
| `BoxPlot(column_name, Target)` | Column, optional data | Visual | Boxplot for outlier detection. |
| `HistPlot(column_name, Target)` | Column, optional data | Visual | Histogram for distribution analysis. |
| `iqr(column_name)` | Column name | (outlier_count, original_count, cleaned_data) | IQR method: values outside 1.5xIQR considered outliers. |
| `capping(column_name)` | Column name | (skewness, affected_count, capped_data) | Winsorization at percentile 99. |
| `log_transform(column_name)` | Column name | (skewness, transformed_data) | Log1p transformation. |
| `z_score_method(column_name, threshold=3)` | Column, threshold | (outlier_count, original_count, cleaned_data) | Z-Score method: values with \|z\| > threshold are outliers. |

### 3.2 Memory Optimisation Functions
| Function | Parameters | Description |
|----------|-----------|-------------|
| `optimize_numeric_data(df)` | DataFrame | Downcasts float64->float32, int64->int8/Int32. |
| `optimize_object_data(df, threshold=0.05)` | DataFrame, threshold | Converts low-cardinality (<5%) object columns to category. |

### 3.3 Notebooks Using `function.py`
| Notebook | Functions Called |
|----------|-----------------|
| `01-LoadData` | `optimize_numeric_data()`, `optimize_object_data()` |
| `03-DataCleaning` | `CleaningData` (`.Duplicate()`, `.BoxPlot()`, `.HistPlot()`, `.iqr()`, `.capping()`, `.z_score_method()`) |

---

## 4. Output Files Summary

| File | Rows | Description |
|------|------|-------------|
| `transactions.parquet` | 14,623,691 | Transaction headers -- after load and validation. |
| `transaction_items.parquet` | 29,246,323 | Items per transaction -- after load and validation. |
| `transactions_capping.parquet` | 14,623,691 | Headers with outliers capped at P99. |
| `transaction_items_cleaned.parquet` | 26,885,688 | Items after duplicate removal. |
| `users_cleaned.parquet` | 2,196,257 | Users after cleaning. |
| `menu_cleaned.parquet` | 8 | Menu without `available_from/to` columns. |
| `stores_cleaned.parquet` | 10 | Store data -- intact. |
| `df_Master_Final.parquet` | 26,885,688 | Item-level master (all tables joined). |
| `df_Master_FE.parquet` | 26,885,688 | Master with engineered features. |
| `df_transaction_features.parquet` | 14,623,691 | Transaction-level features (1 row per transaction). |
| `df_rfm.parquet` | 2,196,257 | RFM per user + scaled features. |
| `df_basket_apriori.parquet` | 9,064,669 | Binary matrix for Apriori. |
| `df_train.parquet` | 11,698,952 | Training set (80% temporal split). |
| `df_test.parquet` | 2,924,739 | Test set (20% temporal split). |
| `df_forecast_90days.parquet` | 900 (90 days x 10 branches) | 90-day forecast output (best model) for Voucher Engine. |

---

## 5. Dependencies

- **Python** 3.12+
- pandas, numpy, matplotlib, seaborn, scipy
- kagglehub (dataset download)
- scikit-learn (StandardScaler, K-Means)
- mlxtend (frequent_patterns Apriori)
- pyarrow (Parquet format)
- statsmodels (ExponentialSmoothing, ARIMA/SARIMA via pmdarima)
- prophet (Facebook Prophet)
- xgboost (gradient-boosted trees)
- pmdarima (auto_arima)

---

## 6. Execution Order

Run notebooks in sequence:

```
01-LoadData.ipynb
02-DataValidation.ipynb
03-DataCleaning.ipynb (or 03-DataCleaning-Rev.ipynb)
04-JoinData.ipynb (or 04-JoinData-Rev.ipynb)
05-FeatureEngineering.ipynb (or 05-FeatureEngineering-Rev.ipynb)
06-EDA.ipynb (or 06-EDA-Rev.ipynb)
06_Modeling_and_Evaluation.ipynb  (consolidated forecasting pipeline)
```

Secondary notebooks (run after 05-FeatureEngineering):
```
K-MeansMember.ipynb + aprioriMember.ipynb
K-MeansNonMember.ipynb + aprioriNonMember.ipynb
```

Legacy notebooks `07.ipynb`, `08-Benchmark-Models.ipynb`, `09_Hybrid_Forecast_HW_XGB.ipynb`, and `09-testingXgb.ipynb` are superseded by `06_Modeling_and_Evaluation.ipynb` and retained for reference only.

Ensure `function.py` is in the same directory. Internet connectivity and Kaggle API credentials are required for `01-LoadData.ipynb`.
