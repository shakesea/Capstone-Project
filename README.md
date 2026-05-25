# G Coffee Shop Transaction Analysis — Capstone Project

Proyek *end-to-end data pipeline* ini menganalisis data transaksi kedai kopi **G Coffee** di Malaysia (Kuala Lumpur, Selangor, Putrajaya) dari **Juli 2023 hingga Juni 2025**. Pipeline mencakup proses **Load → Validate → Clean → Join → Feature Engineering → EDA**, dan menghasilkan dataset siap-pakai untuk **pemodelan RFM**, **Market Basket Analysis (Apriori)**, dan **machine learning (XGBoost)**.

---

## 1. Project Overview

| Aspek | Deskripsi |
|-------|-----------|
| **Tujuan** | Membersihkan, mengintegrasikan, dan merekayasa fitur dari 7 tabel mentah (CSV) menjadi master dataset siap analisis untuk segmentasi pelanggan, analisis keranjang belanja, dan prediksi. |
| **Domain** | Retail *coffee shop chain* — 10 gerai, 8 menu minuman, >14,6 juta transaksi. |
| **Sumber Data** | Kaggle — [G Coffee Shop Transaction 202307 to 202506](https://www.kaggle.com/datasets/geraldooizx/g-coffee-shop-transaction-202307-to-202506) |
| **Cakupan Waktu** | 1 Juli 2023 – 30 Juni 2025 (2 tahun) |
| **Volume Data** | ~14,6M transaksi, ~29,2M *line item*, ~2,2M pengguna terdaftar |
| **Mata Uang** | Ringgit Malaysia (RM) — dikonversi ke IDR (1 RM = Rp3.500) pada saat EDA |

---

## 2. Pipeline Architecture & Workflow

### 2.1 01-LoadData.ipynb — Load & Optimasi Memori

- Mengunduh dataset dari Kaggle via `kagglehub.dataset_download()`.
- Membaca file CSV — 3 tabel terpartisi digabung dengan `glob` + `pd.concat()`:
  - `transactions/*.csv` (14.623.691 baris)
  - `transaction_items/*.csv` (29.246.323 baris)
  - `users/*.csv` (2.196.257 baris)
  - `menu_items.csv`, `stores.csv`, `vouchers.csv`, `payment_methods.csv` (file tunggal).
- **Optimasi Memori** via fungsi dari `function.py`:
  - `optimize_numeric_data()` — downcast `float64→float32`, `int64→int8/Int32`.
  - `optimize_object_data()` — konversi kolom *object* dengan kardinalitas <5% ke `category`.
- **Hasil**: Ukuran memori turun drastis, misal: Transactions 2.915 MB → 669 MB.
- **Output**: File `.parquet` intermediate.

### 2.2 02-DataValidation.ipynb — Standardisasi & Validasi

- **Standardisasi tipe data**:
  - `transaction_id` → `str`
  - `user_id`, `voucher_id` → `Int64` (nullable)
  - `created_at`, `birthdate`, `registered_at` → `datetime64`
  - `valid_from`, `valid_to` → `datetime64`
- **Validasi mendalam** (`run_deep_validation()`):
  | Pemeriksaan | Deskripsi | Hasil |
  |-------------|-----------|-------|
  | Duplikat PK | `transaction_id` duplikat | **0 duplikat** |
  | Integritas FK | `store_id` tidak terdaftar | **0 transaksi** |
  | Tanggal masa depan | `created_at` > hari ini | **0 transaksi** |
  | Umur tidak wajar | Usia saat registrasi <12 atau >100 tahun | **0 user** |
- **Output**: File `.parquet` tervalidasi (tiap tabel).

### 2.3 03-DataCleaning.ipynb — Pembersihan Data

Tahap ini terbagi menjadi beberapa sub-tahap:

#### a. Pemeriksaan Nilai Invalid
- **Orphan Transactions**: User ID transaksi yang tidak ada di tabel Users → **0 baris**.
- **Transaksi nominal negatif**: `original_amount`, `final_amount`, `discount_applied` < 0 → **0 baris**.
- **Item dengan qty/harga negatif** → **0 baris**.
- **Orphan Items**: `transaction_id` tidak ada di header → **0 baris**.
- **Menu tidak terdaftar**: `item_id` tidak ada di `menu_items` → **0 baris**.
- **Konsistensi harga**: `unit_price` berbeda per `item_id` → **0 item**.

#### b. Penanganan Duplikat
- **Duplikat penuh** di `df_TransItem`: **802.939 baris**.
- **Duplikat komposit** `(transaction_id, item_id, created_at)`: **4.645.360 baris**.
- **Kebijakan**: Hapus semua baris dalam grup `(transaction_id, item_id)` dengan selisih waktu ≤ 30 detik → **2.360.635 baris dihapus**.
- **Deterministic dedup (Rev)**: Baris dengan `subtotal` maksimum dipertahankan.
- **Hasil akhir**: 0 duplikat tersisa.

#### c. Rekonsiliasi Header-Detail
- **2.284.725 transaksi** memiliki `original_amount` tidak sinkron dengan `SUM(subtotal)` dari item.
- **Koreksi**: `original_amount` ditimpa dengan `SUM(subtotal)`.
- **Final**: `final_amount = original_amount - discount_applied`.
- **Rev**: `original_amount_header` di-backup sebagai *audit trail* sebelum ditimpa.

#### d. Validasi Diskon
- **Cek diskon negatif**: 784 transaksi dengan diskon > `original_amount` (disebabkan voucher SALES50).
- **Capping**: `discount_applied = min(discount_applied, original_amount)` → **0 transaksi negatif**.
- **Cross-check voucher**: `calculated_discount` dihitung dari *discount_type* dan *discount_value* → **0 mismatch**.

#### e. Outlier Treatment
Tiga metode dibandingkan untuk `final_amount` (skewness awal ≈ 0,53):
| Metode | Data Hilang | Skewness Akhir |
|--------|------------|----------------|
| IQR (1,5×IQR) | 30.633 (0,21%) | 0,50 |
| **Capping (P99)** | **0 (0%)** | **0,49** |
| Z-Score (\|z\|>3) | 30.619 (0,21%) | 0,50 |

**Keputusan**: Metode **Capping di persentil 99** dipilih karena mempertahankan 100% data dengan reduksi skewness terbaik.

#### f. Missing Values
- Kolom `available_from` dan `available_to` pada menu_items dihapus karena 100% null.

### 2.4 04-JoinData.ipynb — Penggabungan Tabel

#### Strategi Join

```
Step 1: df_MasterTrans = df_Trans
    LEFT JOIN df_Users   → ON user_id
    LEFT JOIN df_stores  → ON store_id

Step 2: df_Master = df_TransItem
    LEFT JOIN df_menu          → ON item_id
    LEFT JOIN df_MasterTrans   → ON transaction_id

Step 3: df_Master
    LEFT JOIN df_payment  → ON payment_method_id = method_id
```

#### Validasi Master
- **Row Count**: 26.885.688 baris (sama dengan input).
- **Orphan Check**: 0 untuk menu, store, header.
- **Financial Audit**: 14.623.691 transaksi seimbang (`original_amount = SUM(subtotal)`).
- **Column Cleanup**: Kolom redundan `_x`/`_y` dihapus, `created_at` digabung.

### 2.5 05-FeatureEngineering.ipynb — Rekayasa Fitur

#### a. Fitur Temporal (dari `created_at`)
| Fitur | Logika |
|-------|--------|
| `hour` | `dt.hour` (0–23) |
| `month` | `dt.month` (1–12) |
| `day_name` | `dt.day_name()` |
| `month_name` | `dt.month_name()` |
| `is_weekend` | 'Weekend' jika Sabtu/Minggu, else 'Weekday' |
| `transaction_period` | Morning (5–10), Afternoon (11–15), Evening (16–19), Night (20–23), Late Night (0–4) |

#### b. Fitur Kategorikal
| Fitur | Logika |
|-------|--------|
| `member_status` | `'Member'` jika `user_id NOT NULL`, else `'Guest'` |
| `is_voucher_used` | `'Voucher'` jika `voucher_id NOT NULL`, else `'No Voucher'` |
| `discount_ratio` | `discount_applied / (original_amount + 1e-6)` |

#### c. Agregasi Transaksi → `df_transaction_features`
Group by `transaction_id`:
| Kolom | Agregasi | Nama Baru |
|-------|----------|-----------|
| `quantity` | SUM | `basket_size` |
| `final_amount` | MAX (*deterministic*) | — |
| `discount_applied` | MAX | — |
| `is_weekend_bool` | MAX | — |
| `is_voucher_used_bool` | MAX | — |
| Lainnya | MAX | — |
| `item_id` | COUNT DISTINCT | `item_count` (Rev) |

#### d. RFM Analysis → `df_rfm`
- **Snapshot date**: `MAX(created_at) + 1 day` (2025-07-01).
- **Scope**: Hanya *Member* (`user_id NOT NULL`).
- **Komponen**:
  - **Recency** = (snapshot − last transaction).days
  - **Frequency** = COUNT(transaction_id)
  - **Monetary** = SUM(final_amount)
- **Klasifikasi**:
  - `is_repeat_customer`: 'Repeat Customer' jika Frequency > 1.
- **Scaled RFM (Rev)**: StandardScaler → `RFM_Scaled_Recency`, `RFM_Scaled_Frequency`, `RFM_Scaled_Monetary` (siap K-Means).
- **Boolean flags (Rev)**: `is_weekend_bool`, `is_voucher_used_bool` (0/1).

#### e. Apriori Basket Preparation (Rev)
- Membangun matriks biner `transaction_id × item_name` (1=beli, 0=tidak).
- **Filter**:
  - Hapus item dengan *support* < 0,1% → 0 item dihapus (hanya 8 menu).
  - Hapus transaksi 1-item → 5.559.022 transaksi (38%).
  - Hapus transaksi >30 item → 0 transaksi.
- **Hasil**: Matriks 9.064.669 transaksi × 8 item, sparsity 70,6%.
- **Output**: `df_basket_apriori.parquet`

#### f. Temporal Train/Test Split (Rev)
- **80/20** berdasarkan urutan waktu (`created_at`):
  - **Train**: 11.698.952 transaksi (80%) — 2023-07-01 s.d. 2025-02-04.
  - **Test**: 2.924.739 transaksi (20%) — 2025-02-04 s.d. 2025-06-30.
- **Output**: `df_train.parquet`, `df_test.parquet`

### 2.6 06-EDA.ipynb — Eksplorasi Data

#### Business Overview
| Metrik | Nilai (RM) | Nilai (IDR × Rp3.500) |
|--------|------------|----------------------|
| Total Revenue | ~RM 444.0 juta | ~Rp 1,55 triliun |
| Total Transaksi | 14.623.691 | — |
| Average Transaction Value | ~RM 30,36 | ~Rp 106.260 |
| Member Revenue | ~50% | — |
| Guest Revenue | ~50% | — |

#### Analisis Waktu
- **Daily Revenue Trend**: Grafik revenue vs diskon harian.
- **Hourly Traffic**: Puncak transaksi di jam sibuk; pola weekday vs weekend.
- **Monthly Revenue**: Tren bulanan selama 2 tahun.
- **Revenue by Period**: Setiap periode transaksi (Morning, Afternoon, Evening, Night).

#### Analisis Pelanggan
- **Revenue Split**: ~50% Member vs ~50% Guest.
- **Member Behavior**: ATV member (~RM30,37) vs guest (~RM30,35).
- **Repeat Customer**: 1.536.904 repeaters vs 659.353 one-time.
- **Preference Heatmap**: Proporsi coffee vs non-coffee per member status.

#### Analisis Produk
- **Top 10 Menu**: Berdasarkan quantity terjual.
- **Revenue per Category**: Coffee vs non-coffee.
- **Preference by Period**: Menu favorit per waktu transaksi.
- **Preference by City**: Menu favorit per kota.

#### Analisis Spasial & Pembayaran
- **Revenue by City**: Revenue dan ATV per kota gerai.
- **Payment Analysis**: Revenue per metode pembayaran (cash, card, ewallet).

#### Analisis Promosi
- **Voucher Impact**: Pengaruh voucher terhadap *basket size*.
- **Voucher Sensitivity**: Efektivitas voucher pada Member vs Guest.

#### RFM Segmentation (Rev)
| Segmen | Definisi (R/F/M Quartile) | Jumlah | % |
|--------|--------------------------|--------|---|
| **Champions** | R≥3, F=4, M=4 | 494.866 | 22,5% |
| **Loyal** | F≥3 (bukan Champions) | 334.852 | 15,2% |
| **At Risk** | R=1 | 549.064 | 25,0% |
| **Regular** | Lainnya | 817.475 | 37,2% |

---

## 3. Modul Kustom (`function.py`)

### 3.1 Class `CleaningData`
| Method | Parameter | Return | Deskripsi |
|--------|-----------|--------|-----------|
| `Duplicate(column_name)` | Nama kolom | int | Menghitung jumlah duplikat pada kolom |
| `BoxPlot(column_name, Target)` | Kolom, data opsional | Visual | Plot boxplot untuk deteksi outlier |
| `HistPlot(column_name, Target)` | Kolom, data opsional | Visual | Plot histogram untuk analisis distribusi |
| `iqr(column_name)` | Nama kolom | (outlier_count, original_count, cleaned_data) | Metode IQR: data di luar 1,5×IQR dianggap outlier |
| `capping(column_name)` | Nama kolom | (skewness, affected_count, capped_data) | Winsorization di persentil 99 |
| `log_transform(column_name)` | Nama kolom | (skewness, transformed_data) | Transformasi log1p untuk mengurangi skewness |
| `z_score_method(column_name, threshold=3)` | Kolom, threshold | (outlier_count, original_count, cleaned_data) | Metode Z-Score: data dengan |z|>threshold adalah outlier |

### 3.2 Fungsi Optimasi Memori
| Fungsi | Parameter | Deskripsi |
|--------|-----------|-----------|
| `optimize_numeric_data(df)` | DataFrame | Downcast float64→float32, int64→int8/Int32 |
| `optimize_object_data(df, threshold=0.05)` | DataFrame, threshold | Konversi kolom object kardinalitas rendah (<5%) ke category |

### 3.3 Notebook yang Memanggil `function.py`
| Notebook | Fungsi Dipanggil |
|----------|-----------------|
| `01-LoadData` | `optimize_numeric_data()`, `optimize_object_data()` |
| `03-DataCleaning` | `CleaningData` (`.Duplicate()`, `.BoxPlot()`, `.HistPlot()`, `.iqr()`, `.capping()`, `.z_score_method()`) |
| `03-DataCleaning-Rev` | `CleaningData` (sama dengan di atas) |

---

## 4. Output Files Summary

| File | Baris | Deskripsi |
|------|-------|-----------|
| `transactions.parquet` | 14.623.691 | Header transaksi — setelah load & validasi |
| `transaction_items.parquet` | 29.246.323 | Item per transaksi — setelah load & validasi |
| `transactions_capping.parquet` | 14.623.691 | Header dengan outlier di-capping di P99 |
| `transaction_items_cleaned.parquet` | 26.885.688 | Item tanpa duplikat (baris duplikat dihapus) |
| `users_cleaned.parquet` | 2.196.257 | User setelah pembersihan |
| `menu_cleaned.parquet` | 8 | Menu tanpa kolom `available_from/to` |
| `stores_cleaned.parquet` | 10 | Data store — utuh |
| `df_Master_Final.parquet` | 26.885.688 | Master item-level (semua tabel digabung) |
| `df_Master_FE.parquet` | 26.885.688 | Master + fitur engineering |
| `df_transaction_features.parquet` | 14.623.691 | Agregasi transaksi (1 baris per transaksi) |
| `df_rfm.parquet` | 2.196.257 | RFM per user + scaled features |
| `df_basket_apriori.parquet` | 9.064.669 | Matriks biner untuk Apriori |
| `df_train.parquet` | 11.698.952 | Train set (80% temporal) |
| `df_test.parquet` | 2.924.739 | Test set (20% temporal) |

---

## 5. Dependencies

- **Python** 3.12+
- pandas, numpy, matplotlib, seaborn, scipy
- kagglehub (unduh dataset)
- scikit-learn (StandardScaler — Rev notebook)
- mlxtend (untuk frequent_patterns Apriori — Rev notebook)
- pyarrow (format Parquet)

---

## 6. Cara Menjalankan

Jalankan notebook secara berurutan:

```
01-LoadData.ipynb
02-DataValidation.ipynb
03-DataCleaning.ipynb (atau 03-DataCleaning-Rev.ipynb)
04-JoinData.ipynb (atau 04-JoinData-Rev.ipynb)
05-FeatureEngineering.ipynb (atau 05-FeatureEngineering-Rev.ipynb)
06-EDA.ipynb (atau 06-EDA-Rev.ipynb)
```

Pastikan `function.py` berada di direktori yang sama. Diperlukan koneksi internet dan credentials Kaggle API untuk `01-LoadData.ipynb`.
