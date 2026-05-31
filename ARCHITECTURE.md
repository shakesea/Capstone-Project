# Architecture & Integration Skeleton

## Customer Segmentation + Association Rules + Forecasting Pipeline

### 1. System Overview

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              STREAMLIT APP (app.py)                                       │
│  ┌──────────────────────────┐  ┌───────────────────────────────────────┐                  │
│  │      MEMBER TAB          │  │      NON-MEMBER (GUEST) TAB           │                  │
│  │  · Segment Distribution  │  │  · Segment Distribution               │                  │
│  │  · RFM Profiles + Radar  │  │  · Feature Profiles                   │                  │
│  │  · Rules per Segment     │  │  · Rules per Segment                  │                  │
│  └──────────┬───────────────┘  └──────────┬────────────────────────────┘                  │
└─────────────┼─────────────────────────────┼───────────────────────────────────────────────┘
              │                             │
    ┌─────────▼──────────┐       ┌──────────▼──────────┐
    │  MEMBER MODELS     │       │   GUEST MODELS      │
    │  (member_*.joblib, │       │   (guest_*.joblib,  │
    │   *_member.*)      │       │   *_guest.*)         │
    └─────────┬──────────┘       └──────────┬──────────┘
              │                             │
    ┌─────────▼─────────────────────────────▼──────────┐
    │              PROCESSING LAYER                     │
    │  ┌──────────────────┐  ┌──────────────────────┐  │
    │  │ K-MeansMember    │  │ K-MeansNonMember      │  │
    │  │ (RFM Clustering) │  │ (Transaction Feat.)   │  │
    │  └────────┬─────────┘  └──────────┬───────────┘  │
    │           │                       │               │
    │  ┌────────▼───────────────────────▼───────────┐  │
    │  │       aprioriMember / aprioriNonMember     │  │
    │  │       (Per-Segment Association Rules)       │  │
    │  └────────────────────────────────────────────┘  │
    │                                                  │
    │  ┌────────────────────────────────────────────┐  │
    │  │      06_Modeling_and_Evaluation.ipynb      │  │
    │  │  · Baseline (ARIMA/SARIMA/Prophet)         │  │
    │  │  · XGBoost Supervised Learning             │  │
    │  │  · Hybrid Detrending (HWR/SARIMA/Prophet)  │  │
    │  │  · Comparative Evaluation                  │  │
    │  └──────────────────┬─────────────────────────┘  │
    └─────────────────────┼────────────────────────────┘
                          │
    ┌─────────────────────▼────────────────────────────┐
    │                 DATA LAYER                        │
    │  · df_transaction_features.parquet (14.6M rows)  │
    │  · df_basket_apriori.parquet (9.1M rows, 8 prods)│
    │  · df_rfm-Member.parquet (2.2M rows)             │
    │  · df_forecast_90days.parquet (900 rows)         │
    │                                                  │
    │                    ↓                              │
    │            VOUCHER ENGINE                        │
    │         (S_time, S_margin)                       │
    └──────────────────────────────────────────────────┘
```

---

### 2. Data Layer (Source Files)

| File | Rows | Columns | Content |
|---|---|---|---|
| `df_transaction_features.parquet` | 14,623,691 | 17 | All transactions (member + guest) with features |
| `df_basket_apriori.parquet` | 9,064,669 | 9 | One-hot encoded 8 beverage products per transaction_id |
| `df_rfm-Member.parquet` | 2,196,257 | 5 | RFM per member (Recency, Frequency, Monetary, user_id, is_repeat_customer) |
| `df_forecast_90days.parquet` | 900 | 3 | 90-day forecast per branch (best model output) |

**Note:** `df_transaction_features.parquet` uses categorical dtypes that cause pandas `read_parquet()` to fail. **Must read with PyArrow** (`pq.read_table()`).

---

### 3. Processing Layer (Notebooks)

#### 3a. K-MeansMember.ipynb — Member RFM Clustering

```
Input:  df_rfm-Member.parquet
        └─ columns: [user_id, Recency, Frequency, Monetary, is_repeat_customer]

Pipeline:
  1. Load RFM data (pandas read_parquet — aman, no categorical issue)
  2. Feature Transforms (7 methods):
       - No Transform (raw)
       - Log1p
       - Log1p → StandardScaler
       - Log1p → MinMaxScaler
       - QuantileTransformer (n_quantiles=1000, output_distribution='normal')
       - PowerTransformer (Yeo-Johnson)
       - PowerTransformer (Box-Cox after shift)
  3. MiniBatchKMeans (batch_size=8192, n_init=3, random_state=42)
     → Loop k=2..10, pick best via Silhouette + DBI
  4. PCA (2D) for visualization
  5. HDBSCAN for label refinement
  6. Segment naming (manual mapping)
  7. Profile aggregation (R/F/M means per cluster)

Output:
  ├── model_kmeans_member.joblib     (MiniBatchKMeans object)
  ├── scaler_member.joblib           (best quantile scaler)
  ├── member_cluster_metadata.json   (segment labels, profiles, k, silhouette)
  └── df_member_with_segments.parquet (user_id + RFM + cluster + segment_name)
        └─ columns: [user_id, Recency, Frequency, Monetary, is_repeat_customer, cluster, segment_name]
```

#### 3b. K-MeansNonMember.ipynb — Guest Transaction Clustering

```
Input:  df_transaction_features.parquet
        └─ filter: user_id.isna() → ~7.3M guest transactions
        └─ features: [final_amount, basket_size, item_count, hour,
                      is_weekend_bool, is_voucher_used_bool, discount_ratio]

Pipeline: (same structure as Member, different features)
  1. Load via PyArrow (avoid categorical crash)
  2. Filter guest (user_id IS NULL)
  3. Feature transforms (7 methods)
  4. MiniBatchKMeans (k determined via elbow)
  5. PCA + HDBSCAN
  6. Segment naming: Big Spender, Weekend Visitor, Deal Hunter, Quick Buy
  7. Save model + scaler + metadata

Output:
  ├── model_kmeans_guest.joblib       (MiniBatchKMeans object)
  ├── scaler_guest.joblib             (best scaler)
  ├── guest_cluster_metadata.json     (segment labels, cluster_cols, optimal_k)
  └── df_guest_with_segments.parquet  (transaction_id + features + cluster + segment_name)
        └─ columns: [transaction_id, ..., cluster, cluster_normalized, segment_name]
```

#### 3c. aprioriMember.ipynb — Member Association Rules (per Segment)

```
Input:
  ├── df_basket_apriori.parquet       (9M basket-product rows)
  ├── df_transaction_features.parquet (for user_id + member_status join)
  └── df_member_with_segments.parquet (for segment_name join via user_id)

Join Chain:
  basket_table ──(transaction_id)──→ tx_table ──(user_id)──→ seg_table
                                           │
                                    filter member_status='Member'

Apriori:
  For each segment:
    df_seg = filter(segment_name == seg)
    frequent_itemsets = apriori(df_seg, min_support=0.01, use_colnames=True)
    rules = association_rules(frequent_itemsets, metric='confidence', min_threshold=0.1)
    rules['segment_name'] = seg

Output:
  ├── df_rules_member.parquet   (224 rules, 4 segments, 15 columns)
  └── df_rules_member.csv       (same, CSV)

Note: Lift < 1.0 (~0.70) for all rules — beverages are bought singly.
      Using confidence metric to capture all 56 pairwise rules per segment.
```

#### 3d. aprioriNonMember.ipynb — Guest Association Rules (per Segment)

```
Input:
  ├── df_basket_apriori.parquet          (9M basket-product rows)
  ├── df_transaction_features.parquet    (for member_status join)
  └── df_guest_with_segments.parquet     (for segment_name join)

Join Chain:
  basket_table ──(transaction_id)──→ tx_table ──(transaction_id)──→ gseg_table
                                           │
                                    filter member_status='Guest'

Apriori:
  For each segment:
    df_seg = filter(segment_name == seg)
    frequent_itemsets = apriori(df_seg, min_support=0.01, use_colnames=True)
    rules = association_rules(frequent_itemsets, metric='confidence', min_threshold=0.1)

Output:
  ├── df_rules_guest.parquet   (168 rules, 3 segments, 15 columns)
  └── df_rules_guest.csv       (same, CSV)

Note: Guest has 4 segments but Apriori produces rules for only 3
      (Big Spender, Weekend Visitor, Deal Hunter).
      "Quick Buy" has no beverage items in baskets → no rules.
```

#### 3e. 06_Modeling_and_Evaluation.ipynb — Forecasting Pipeline (Consolidated)

```
Input:  df_transaction_features.parquet
        └─ aggregated daily per city:
           [total_transactions, total_revenue, avg_basket,
            voucher_rate, lag_1, lag_7, rolling_avg_7,
            day_of_week, month, created_at, city]

Pipeline (4 sections):
  A. BASELINE MODELS (univariate, per branch)
     1. ARIMA - auto_arima(seasonal=False, stepwise=True)
     2. SARIMA - auto_arima(seasonal=True, m=7)
     3. Prophet - weekly_seasonality=True
     Metrics: MAE, RMSE, MAPE per branch; aggregate across 10 branches

  B. XGBoost SUPERVISED (pooled, multivariate)
     Features: [lag_1, lag_7, rolling_avg_7, day_of_week,
                month, voucher_rate, city_onehot]
     Train/test split: 2025-03-25 (80/20 temporal)
     Feature importance (gain-based)
     Residual diagnostics

  C. HYBRID DETRENDING ARCHITECTURES
     1. Holt-Winters (additive, seasonal_periods=365)
        └─ XGBoost on residuals [day_of_week, month, voucher_rate]
     2. SARIMA (1,0,1)(1,0,1,7)
        └─ XGBoost on residuals (same features)
     3. Prophet (weekly)
        └─ XGBoost on residuals (same features)
     Rationale: Non-autoregressive residual features avoid
                low-pass recursive forecast collapse

  D. EVALUATION AND OUTPUT
     Cross-architecture comparison (MAE, RMSE, R2, MAPE)
     Best model selection -> 90-day forecast
     Variability check (std/mean per branch)

Output:
  └── df_forecast_90days.parquet
        └─ columns: [branch, created_at, total_transactions]

Consumption:
  -> Voucher Engine (S_time, S_margin dynamic scoring)
```

**Key design decision**: XGBoost on residuals uses only `day_of_week`, `month`, and `voucher_rate` — autoregressive features (`lag_1`, `rolling_avg_7`) are excluded to prevent error accumulation in multi-step recursive forecasting.

**Supersedes**: Legacy notebooks `07.ipynb`, `08-Benchmark-Models.ipynb`, `09_Hybrid_Forecast_HW_XGB.ipynb`, and `09-testingXgb.ipynb`. These remain on disk but are no longer part of the active pipeline.

---

### 4. Model Layer (Saved Artifacts)

#### 4a. Naming Convention

```
┌───────────────────────┬──────────────────────┬──────────────────────┐
│ Artifact              │ Member Prefix        │ Guest Prefix         │
├───────────────────────┼──────────────────────┼──────────────────────┤
│ KMeans model          │ model_kmeans_member  │ model_kmeans_guest   │
│ Scaler/Transform      │ scaler_member        │ scaler_guest         │
│ Cluster metadata      │ member_cluster_meta  │ guest_cluster_meta   │
│ Segment data          │ df_member_with_seg.. │ df_guest_with_seg..  │
│ Association rules     │ df_rules_member      │ df_rules_guest       │
└───────────────────────┴──────────────────────┴──────────────────────┘
```

#### 4b. Metadata Contracts

**member_cluster_metadata.json**
```json
{
  "model_type": "MiniBatchKMeans",
  "k": 2,
  "features": ["Recency", "Frequency", "Monetary"],
  "best_transform": "Quantile",
  "silhouette_score": 0.454,
  "total_members": 2196257,
  "cluster_labels": {
    "0": "At Risk Regulars",
    "1": "New Occasional",
    "2": "Hibernating",
    "3": "Champions"
  },
  "cluster_profiles": [
    {
      "cluster": 0,
      "count": 399069,
      "pct": 18.17,
      "revenue_share_pct": 44.0,
      "R_mean": 95.7, "F_mean": 7.8, "M_mean": 249.6,
      "R_median": 82.0, "F_median": 7.0, "M_median": 224.5,
      "monetary_sum": 99625920.0
    }
  ]
}
```

**guest_cluster_metadata.json**
```json
{
  "model_type": "MiniBatchKMeans",
  "optimal_k": 4,
  "cluster_cols": [
    "final_amount", "basket_size", "item_count", "hour",
    "is_weekend_bool", "is_voucher_used_bool", "discount_ratio"
  ],
  "best_transform": "Quantile",
  "cluster_id_to_name": {
    "0": "Big Spender",
    "1": "Weekend Visitor",
    "2": "Deal Hunter",
    "3": "Quick Buy"
  }
}
```

---

### 5. Application Layer (app.py)

#### 5a. Component Architecture

```
app.py
├── @st.cache_data
│   ├── load_json(path)         → dict
│   ├── load_rules(path)        → pd.DataFrame
│   └── load_segment_counts(path, col) → pd.DataFrame
│
├── Sidebar
│   └── radio("Select View")
│       ├── "Member"
│       └── "Non-Member (Guest)"
│
├── Member Tab
│   ├── Metrics (total, k, silhouette, transform)
│   ├── Segment Distribution (pie chart + table)
│   ├── Segment Profiles (RFM means table)
│   ├── RFM Radar (normalized, per segment)
│   ├── Association Rules
│   │   ├── Segment selector (dropdown)
│   │   ├── Filter: min_lift, min_confidence (sliders)
│   │   ├── Rules table (sortable)
│   │   └── Top 15 lift bar chart
│   └── Model Info (expandable JSON)
│
└── Guest Tab
    ├── Metrics (total, k, model)
    ├── Segment Distribution (pie chart + table)
    ├── Cluster Features (list + segment names)
    ├── Association Rules (same structure as Member)
    │   └── Handles empty rules gracefully
    └── Model Info (expandable JSON)
```

#### 5b. Data Loading Strategy

| Component | Source | Method |
|---|---|---|
| Segment counts | `*_with_segments.parquet` | `pq.read_table(columns=['segment_name'])` + Counter |
| Segment profiles | `*_cluster_metadata.json` | Direct `json.load` |
| Association rules | `df_rules_*.parquet` | `pd.read_parquet` (small data, <300 rows) |
| Model info | `*_cluster_metadata.json` | `json.load` |
| Visualizations | Computed from above | Plotly charts |

**Performance:** `load_segment_counts()` reads only 1 column from multi-million-row parquet → memory efficient.

---

### 6. Data Flow Diagram

```
Source                              Processing                          Output
────────────────────────────────────────────────────────────────────────────────────

df_rfm-Member.parquet ──→ K-MeansMember.ipynb ──→ model_kmeans_member.joblib
                                                     scaler_member.joblib
                                                     member_cluster_metadata.json
                                                     df_member_with_segments.parquet
                                                                │
df_basket_apriori.parquet ──→ aprioriMember.ipynb ─────────────┤
df_transaction_features.parquet                                │
                                                                ├──→ app.py (Member tab)
                                                                │
df_rules_member.parquet ←──────────────────────────────────────┘


df_transaction_features.parquet ──→ K-MeansNonMember.ipynb ──→ model_kmeans_guest.joblib
(fitur guest, user_id IS NULL)                                    scaler_guest.joblib
                                                                    guest_cluster_metadata.json
                                                                    df_guest_with_segments.parquet
                                                                               │
df_basket_apriori.parquet ──→ aprioriNonMember.ipynb ────────────────────────┤
df_transaction_features.parquet                                               │
                                                                               ├──→ app.py (Guest tab)
                                                                               │
df_rules_guest.parquet ←─────────────────────────────────────────────────────┘


df_transaction_features.parquet ──→ 06_Modeling_and_Evaluation.ipynb ──→ df_forecast_90days.parquet
(daily aggregation)                                                             │
                                                                                ├──→ Voucher Engine
                                                                                │   (S_time, S_margin)
                                                                                │
                                                                          model artifacts:
                                                                          ├── hw_models (dict of ExponentialSmoothing)
                                                                          ├── xgb_model (XGBRegressor)
                                                                          ├── xgb_residual (XGBRegressor)
                                                                          ├── sar_macro_models (dict of ARIMA)
                                                                          └── prop_macro_models (dict of Prophet)
```

---

### 7. Integration Contracts

#### 7a. Join Keys

| Notebook | Left Table | Right Table | Join Key | Type |
|---|---|---|---|---|
| aprioriMember | basket_table | tx_table | `transaction_id` | inner |
| aprioriMember | member_tbl | seg_table | `user_id` | left outer |
| aprioriNonMember | basket_table | tx_table | `transaction_id` | inner |
| aprioriNonMember | guest_tbl | gseg_table | `transaction_id` | left outer |

#### 7b. Column Contracts

**df_rules_member.parquet / df_rules_guest.parquet**
```
antecedents        object   (set converted to comma-separated string)
consequents        object   (set converted to comma-separated string)
support            float64  (P(A ∪ B) / total)
confidence         float64  (P(B | A))
lift               float64  (confidence / P(B))
leverage           float64
conviction         float64
zhangs_metric      float64
jaccard            float64
certainty          float64
kulczynski         float64
representativity   float64
antecedent support float64  (P(A))
consequent support float64  (P(B))
segment_name       object   (segment identifier)
```

#### 7c. Critical Rules

1. **Always use PyArrow** when reading `df_transaction_features.parquet` (categorical dtype crash).
2. **Never remove `segment_name`** from rules DataFrames — it's the primary join key for the app.
3. **All lift ~0.70** — beverages are rarely co-purchased. Use `metric='confidence'` with low threshold.
4. **Guest "Quick Buy" segment** may have no Apriori rules — app must handle empty gracefully.

---

### 8. Extensibility

#### Adding a New Segment Type
1. Create new K-Means notebook → follow `K-Means*.ipynb` template
2. New parquet output: `df_<type>_with_segments.parquet`
3. New Apriori notebook → copy structure, adjust join key
4. New rules file: `df_rules_<type>.parquet`
5. Add new tab in `app.py` following existing pattern

#### Adding New Products to Basket
1. Add int8 flag column to `df_basket_apriori.parquet`
2. No code changes needed — notebooks auto-detect product columns

#### Updating Segment Labels
1. Edit the segment mapping in K-Means notebook
2. Re-run notebook → updates metadata JSON + segment parquet
3. Re-run Apriori → updates rules with new segment names
4. App reads dynamically — no code changes needed
