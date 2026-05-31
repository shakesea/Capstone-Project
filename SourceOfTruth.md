# Source of Truth: Data Dictionary & Data Governance
## G Coffee Shop — Decision Support System (DSS)

Dokumen ini berfungsi sebagai **Data Catalog, Skema Data, dan Kebijakan Integritas Data**. Seluruh informasi didasarkan pada kode riil di notebook pipeline dan file `.parquet` yang dihasilkan.

---

## 1. Data Dictionary & Kegunaan Tabel

### 1.1 Tabel Sumber (Source Tables)

#### transactions.parquet — Header Transaksi
**Baris**: 14.623.691 | **Kegunaan**: Informasi ringkas setiap struk pembelian (store, payment, voucher, user, nominal).

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `transaction_id` | string (UUID) | Primary Key — ID unik setiap transaksi |
| `store_id` | int8 | Foreign Key ke `stores` — gerai tempat transaksi |
| `payment_method_id` | int8 | Foreign Key ke `payment_methods` — metode bayar |
| `voucher_id` | Int64 (nullable) | Foreign Key ke `vouchers` — kode promo (NULL jika tidak ada) |
| `user_id` | Int64 (nullable) | Foreign Key ke `users` — ID member (NULL jika guest) |
| `original_amount` | float32 | Nilai sebelum diskon (telah direkonsiliasi dengan SUM subtotal item) |
| `discount_applied` | float32 | Nilai diskon yang diterapkan (telah di-capping agar ≤ original_amount) |
| `final_amount` | float32 | Nilai akhir setelah diskon: `original_amount - discount_applied` |
| `created_at` | datetime64[ns] | Waktu transaksi terjadi |

#### transaction_items.parquet — Detail Item Transaksi
**Baris**: 29.246.323 | **Kegunaan**: Setiap baris adalah satu *line item* dalam suatu transaksi.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `transaction_id` | string (UUID) | Foreign Key ke `transactions` — ID struk induk |
| `item_id` | int8 | Foreign Key ke `menu_items` — ID menu yang dibeli |
| `quantity` | int8 | Jumlah unit item ini dalam transaksi (min 1, max 3) |
| `unit_price` | float32 | Harga per unit saat transaksi (RM) |
| `subtotal` | float32 | Total baris: `quantity × unit_price` |
| `created_at` | datetime64[ns] | Waktu transaksi (sama dengan header) |

#### users.parquet — Data Pelanggan
**Baris**: 2.196.257 | **Kegunaan**: Profil demografis pengguna terdaftar.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `user_id` | Int64 | Primary Key — ID unik pelanggan |
| `gender` | string (object) | Jenis kelamin: 'male' / 'female' |
| `birthdate` | datetime64[ns] | Tanggal lahir (1964-07-21 s.d. 2009-07-19) |
| `registered_at` | datetime64[ns] | Waktu pendaftaran akun |

#### stores.parquet — Data Gerai
**Baris**: 10 | **Kegunaan**: Informasi 10 gerai G Coffee di Malaysia.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `store_id` | int8 | Primary Key — ID gerai |
| `store_name` | string | Nama gerai (misal: 'G Coffee @ USJ 89q') |
| `street` | string | Alamat jalan |
| `postal_code` | string (object) | Kode pos (disimpan sebagai object untuk mempertahankan leading zeros) |
| `city` | string | Kota/distrik (10 nilai unik) |
| `state` | string | Negara bagian (3 nilai: Kuala Lumpur, Selangor Darul Ehsan, Putrajaya) |
| `latitude` | float32 | Koordinat latitude |
| `longitude` | float32 | Koordinat longitude |

#### menu_items.parquet — Katalog Menu
**Baris**: 8 | **Kegunaan**: Daftar 8 minuman yang dijual.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `item_id` | int8 | Primary Key — ID menu |
| `item_name` | string | Nama minuman: Espresso, Americano, Latte, Cappuccino, Flat White, Mocha, Hot Chocolate, Matcha Latte |
| `category` | string | Kategori: 'coffee' (6 item) / 'non-coffee' (2 item) |
| `price` | float32 | Harga menu standar (RM 6,0–10,0) |
| `is_seasonal` | bool | Apakah item musiman (semua False) |

> **Catatan**: Kolom `available_from` dan `available_to` telah **dihapus** di notebook `03-DataCleaning` karena 100% bernilai NULL.

#### vouchers.parquet — Kupon Diskon
**Baris**: 16 | **Kegunaan**: Master data voucher promo.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `voucher_id` | int64 | Primary Key |
| `voucher_code` | string | Kode promo: SALES77, SALES88, SALES99, SALES10, SALES11, MERDEKA, SALES66, SALES50 |
| `discount_type` | string | Tipe: 'percentage' (14 voucher) / 'fixed' (2 voucher MERDEKA) |
| `discount_value` | float64 | Nilai diskon: 5,0–50,0 (persen untuk percentage, nominal untuk fixed) |
| `valid_from` | datetime64[ns] | Tanggal mulai berlaku |
| `valid_to` | datetime64[ns] | Tanggal akhir berlaku |

#### paymentsUnique.parquet — Metode Pembayaran
**Baris**: 5 | **Kegunaan**: Jenis pembayaran yang tersedia.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `method_id` | int64 | Primary Key |
| `method_name` | string | Nama: 'cash', 'credit_card', 'debit_card', 'tng', 'grabpay' |
| `category` | string | Kategori: 'cash', 'card', 'ewallet' |

---

### 1.2 Tabel Hasil Pembersihan (Cleaned Outputs)

#### transactions_capping.parquet
- Header transaksi setelah outlier di-capping (P99).
- Ditambahkan kolom: `Non-Member` (bool), `Member` (bool), `voucher_code`, `discount_type`, `discount_value`, `valid_from`, `valid_to`, `calculated_discount`.
- **Rev** (`03-DataCleaning-Rev`): Ditambahkan `original_amount_header` sebagai *audit trail* — backup nilai `original_amount` sebelum direkonsiliasi.

#### transaction_items_cleaned.parquet
- Duplikat baris (selisih waktu ≤ 30 detik dalam grup `transaction_id, item_id`) telah dihapus.
- **Baris**: 26.885.688 (turun dari 29.246.323).

#### users_cleaned.parquet
- Baris dengan `birthdate` atau `registered_at` di masa depan telah dihapus.
- **Baris**: 2.196.257 (tidak ada perubahan jumlah — 0 baris dihapus).

#### menu_cleaned.parquet
- Kolom `available_from` dan `available_to` dihapus.
- **Baris**: 8.

#### stores_cleaned.parquet
- Identik dengan `stores.parquet`. **Baris**: 10.

---

### 1.3 Tabel Master & Feature Engineering

#### df_Master_Final.parquet — Master Item-Level (26.885.688 baris)
**Kegunaan**: Tabel denormalisasi utama — setiap baris adalah satu *line item* yang diperkaya dengan semua informasi dari tabel lain.

| Kolom | Tipe Data | Sumber Tabel | Deskripsi |
|-------|-----------|-------------|-----------|
| `transaction_id` | string | transactions | ID unik transaksi |
| `item_id` | int8 | transaction_items | ID menu |
| `quantity` | int8 | transaction_items | Jumlah unit |
| `unit_price` | float32 | transaction_items | Harga per unit |
| `subtotal` | float32 | transaction_items | Subtotal baris |
| `item_name` | string | menu_items | Nama menu |
| `menu_category` | string | menu_items | Kategori menu (di-rename dari `category_x`) |
| `price` | float32 | menu_items | Harga master menu |
| `is_seasonal` | bool | menu_items | Flag musiman |
| `store_id` | int8 | transactions | ID gerai |
| `payment_method_id` | int8 | transactions | ID metode bayar |
| `voucher_id` | Int64 (nullable) | transactions | ID voucher |
| `user_id` | Int64 (nullable) | transactions | ID user |
| `original_amount` | float32 | transactions | Nilai asli (sudah direkonsiliasi) |
| `discount_applied` | float32 | transactions | Diskon diterapkan (sudah di-capping) |
| `final_amount` | float32 | transactions | Nilai akhir |
| `original_amount_header` | float32 | *Rev only* | Backup original_amount sebelum rekonsiliasi |
| `voucher_code` | string | vouchers | Kode voucher |
| `discount_type` | string | vouchers | Tipe diskon |
| `discount_value` | float32 | vouchers | Nilai diskon master |
| `valid_from` | datetime64 | vouchers | Masa berlaku mulai |
| `valid_to` | datetime64 | vouchers | Masa berlaku selesai |
| `calculated_discount` | float32 | — | Kalkulasi diskon sesuai aturan voucher (*audit column*) |
| `gender` | string | users | Jenis kelamin |
| `birthdate` | datetime64 | users | Tanggal lahir |
| `registered_at` | datetime64 | users | Waktu registrasi |
| `store_name` | string | stores | Nama gerai |
| `street` | string | stores | Alamat |
| `postal_code` | string | stores | Kode pos |
| `city` | string | stores | Kota |
| `state` | string | stores | Negara bagian |
| `latitude` | float32 | stores | Latitude |
| `longitude` | float32 | stores | Longitude |
| `created_at` | datetime64 | transactions | Waktu transaksi |
| `method_name` | string | payment_methods | Nama metode bayar |
| `payment_category` | string | payment_methods | Kategori pembayaran (di-rename dari `category_y`) |

#### df_Master_FE.parquet — Master dengan Fitur Engineering
**Baris**: 26.885.688 | **Kegunaan**: Sama dengan `df_Master_Final` + fitur tambahan.

**Fitur tambahan**:
| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `hour` | int32 | Jam transaksi (0–23) |
| `month` | int32 | Bulan transaksi (1–12) |
| `day_name` | string | Nama hari (Monday–Sunday) |
| `month_name` | string | Nama bulan (January–December) |
| `is_weekend` | string | 'Weekend' / 'Weekday' |
| `member_status` | string | 'Member' / 'Guest' |
| `is_voucher_used` | string | 'Voucher' / 'No Voucher' |
| `transaction_period` | string | 'Morning' / 'Afternoon' / 'Evening' / 'Night' / 'Late Night' |
| `discount_ratio` | float64 | `discount_applied / (original_amount + 1e-6)` |
| `is_weekend_bool` | int8 | *Rev only* — 1 jika weekend, 0 jika tidak |
| `is_voucher_used_bool` | int8 | *Rev only* — 1 jika pakai voucher, 0 jika tidak |

#### df_transaction_features.parquet — Fitur per Transaksi
**Baris**: 14.623.691 | **Kegunaan**: Satu baris per transaksi — siap untuk pemodelan.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `transaction_id` | string | ID unik transaksi (Primary Key tabel ini) |
| `basket_size` | int64 | Total item dalam transaksi (SUM quantity) |
| `final_amount` | float32 | Nilai akhir yang dibayar |
| `discount_applied` | float32 | Diskon yang diterapkan |
| `is_weekend` | string | 'Weekend' / 'Weekday' |
| `is_voucher_used` | string | 'Voucher' / 'No Voucher' |
| `hour` | int64 | Jam transaksi |
| `month_name` | string | Nama bulan |
| `day_name` | string | Nama hari |
| `city` | string | Kota gerai |
| `method_name` | string | Metode pembayaran |
| `payment_category` | string | Kategori pembayaran |
| `member_status` | string | 'Member' / 'Guest' |
| `created_at` | datetime64[ns] | Waktu transaksi |
| `user_id` | Int64 (nullable) | ID user |
| `transaction_period` | string | Periode transaksi |
| `item_count` | int64 | *Rev only* — Jumlah item unik dalam transaksi |
| `is_weekend_bool` | int8 | *Rev only* — Boolean weekend |
| `is_voucher_used_bool` | int8 | *Rev only* — Boolean voucher |

#### df_rfm.parquet — RFM per Pelanggan
**Baris**: 2.196.257 | **Kegunaan**: Segmentasi RFM untuk analisis loyalitas.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `user_id` | Int64 | ID unik pelanggan (Primary Key) |
| `Recency` | int64 | Hari sejak transaksi terakhir (dari snapshot date 2025-07-01) |
| `Frequency` | int64 | Total jumlah transaksi |
| `Monetary` | float64 | Total revenue dari pelanggan ini (RM) |
| `is_repeat_customer` | string | 'Repeat Customer' (Frequency > 1) atau 'One-Time Customer' |
| `RFM_Scaled_Recency` | float64 | *Rev only* — Recency setelah StandardScaler (z-score) |
| `RFM_Scaled_Frequency` | float64 | *Rev only* — Frequency setelah StandardScaler |
| `RFM_Scaled_Monetary` | float64 | *Rev only* — Monetary setelah StandardScaler |

#### df_basket_apriori.parquet — Matriks Basket untuk Apriori
**Baris**: 9.064.669 | **Kolon**: 8 (satu per item menu) | **Kegunaan**: Matriks biner untuk *frequent pattern mining*.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `transaction_id` | string (index) | ID transaksi (row index) |
| `Espresso` | int8 | 1 jika dibeli, 0 jika tidak |
| `Americano` | int8 | 1 jika dibeli, 0 jika tidak |
| `Latte` | int8 | 1 jika dibeli, 0 jika tidak |
| `Cappuccino` | int8 | 1 jika dibeli, 0 jika tidak |
| `Flat White` | int8 | 1 jika dibeli, 0 jika tidak |
| `Mocha` | int8 | 1 jika dibeli, 0 jika tidak |
| `Hot Chocolate` | int8 | 1 jika dibeli, 0 jika tidak |
| `Matcha Latte` | int8 | 1 jika dibeli, 0 jika tidak |

> **Sparsity**: 70,59% — hanya 29,41% sel yang bernilai 1.

#### df_train.parquet & df_test.parquet — Split Temporal
| File | Baris | Periode Waktu |
|------|-------|---------------|
| `df_train.parquet` | 11.698.952 (80%) | 2023-07-01 s.d. 2025-02-04 14:33:48 |
| `df_test.parquet` | 2.924.739 (20%) | 2025-02-04 14:33:49 s.d. 2025-06-30 19:59:39 |

**Skema**: Identik dengan `df_transaction_features.parquet`.

#### df_forecast_90days.parquet — Forecast Output untuk Voucher Engine
**Baris**: 900 (90 hari x 10 cabang) | **Kegunaan**: Prediksi 90 hari ke depan `total_transactions` per cabang.

| Kolom | Tipe Data | Deskripsi |
|-------|-----------|-----------|
| `branch` | string | Nama cabang (city) |
| `created_at` | datetime64[ns] | Tanggal prediksi |
| `total_transactions` | float64 | Prediksi jumlah transaksi (tepat setelah rekonstruksi T_makro + Residual_pred) |

> **Asal**: Notebook `06_Modeling_and_Evaluation.ipynb` — model hybrid terbaik dipilih berdasarkan MAE test set terendah.

---

## 2. Hubungan Antar Tabel (Relational Mapping & Keys)

### 2.1 Entity Relationship Diagram (ERD)

```
┌────────────┐       ┌──────────────────┐       ┌──────────┐
│   stores   │       │  transactions    │       │  users   │
│────────────│       │──────────────────│       │──────────│
│ store_id PK├──┐    │ transaction_id PK│       │ user_id  │
│ store_name │  │    │ store_id    FK───┼──┐    │ gender   │
│ city       │  │    │ payment_method_id│  │    │ birthdate│
│ state      │  │    │ voucher_id  FK───┼──┐    │ reg_date │
│ ...        │  │    │ user_id     FK───┼──┤    └──────────┘
└────────────┘  │    │ original_amount  │  │         │
                │    │ discount_applied │  │         │
                │    │ final_amount     │  │         │
                │    │ created_at       │  │         │
                │    └────────┬─────────┘  │         │
                │             │            │         │
                │    ┌────────┴─────────┐  │         │
                │    │ transaction_items │  │         │
                │    │──────────────────│  │         │
                │    │ item_id     FK───┼──┼─────────┘
                │    │ transaction_id   │  │
                │    │ quantity         │  │
                │    │ unit_price       │  │
                │    │ subtotal         │  │
                │    │ created_at       │  │
                │    └────────┬─────────┘  │
                │             │            │
                │    ┌────────┴─────────┐  │
                │    │   menu_items     │  │
                │    │──────────────────│  │
                │    │ item_id     PK   │  │
                │    │ item_name       │  │
                │    │ category        │  │
                │    │ price           │  │
                │    └──────────────────┘  │
                │                          │
        ┌───────┴──────────┐     ┌─────────┴──────────┐
        │ payment_methods  │     │     vouchers        │
        │──────────────────│     │─────────────────────│
        │ method_id    PK  │     │ voucher_id     PK   │
        │ method_name      │     │ voucher_code        │
        │ category         │     │ discount_type       │
        └──────────────────┘     │ discount_value      │
                                 │ valid_from          │
                                 │ valid_to            │
                                 └─────────────────────┘
```

### 2.2 Primary Keys (PK) & Foreign Keys (FK)

| Tabel | Primary Key | Tipe Data | Keterangan |
|-------|-------------|-----------|------------|
| `transactions` | `transaction_id` | string (UUID) | PK unik |
| `transaction_items` | — | — | Tidak ada PK tunggal (composite key: `transaction_id` + `item_id` + `created_at`) |
| `users` | `user_id` | Int64 | PK unik |
| `stores` | `store_id` | int8 | PK unik (10 gerai) |
| `menu_items` | `item_id` | int8 | PK unik (8 item) |
| `vouchers` | `voucher_id` | int64 | PK unik (16 voucher) |
| `payment_methods` | `method_id` | int64 | PK unik (5 metode) |

| FK | Tabel Asal (Child) | Tabel Tujuan (Parent) | Kolom Penghubung |
|----|--------------------|-----------------------|-----------------|
| FK1 | `transactions` | `stores` | `store_id` |
| FK2 | `transactions` | `payment_methods` | `payment_method_id` → `method_id` |
| FK3 | `transactions` | `vouchers` | `voucher_id` |
| FK4 | `transactions` | `users` | `user_id` |
| FK5 | `transaction_items` | `transactions` | `transaction_id` |
| FK6 | `transaction_items` | `menu_items` | `item_id` |

### 2.3 Kardinalitas

| Relationship | Kardinalitas | Business Logic |
|-------------|--------------|----------------|
| `stores` → `transactions` | **One-to-Many** | Satu gerai memiliki banyak transaksi. |
| `users` → `transactions` | **One-to-Many** | Satu pelanggan dapat melakukan banyak transaksi. Nullable (guest). |
| `payment_methods` → `transactions` | **One-to-Many** | Satu metode pembayaran dipakai di banyak transaksi. |
| `vouchers` → `transactions` | **One-to-Many** | Satu voucher dipakai di banyak transaksi. Nullable. |
| `transactions` → `transaction_items` | **One-to-Many** | Satu transaksi memiliki banyak *line item*. Join via `transaction_id`. |
| `menu_items` → `transaction_items` | **One-to-Many** | Satu menu dapat muncul di banyak *line item* transaksi. |

### 2.4 Catatan Integritas Referensial

- **Validity Check**: 0 transaksi dengan `store_id` tidak terdaftar (validasi di notebook `02-DataValidation`).
- **Orphan Items**: 0 *line item* dengan `transaction_id` tidak ada di header (validasi di `03-DataCleaning`).
- **Orphan Menu**: 0 *line item* dengan `item_id` tidak terdaftar di menu (validasi di `03-DataCleaning`).
- **Orphan Users**: 0 transaksi dengan `user_id` tidak terdaftar di users (validasi di `03-DataCleaning`).

---

## 3. Logika Transformasi & Lineage

### 3.1 Lineage: Raw CSVs → Master Dataset

```
Raw CSV (Kaggle)
  │
  ▼ 01-LoadData
  ├── Gabungkan file CSV terpartisi
  ├── Optimasi memori (downcast, category)
  └── Simpan sebagai .parquet
  │
  ▼ 02-DataValidation
  ├── Standardisasi tipe data (datetime, Int64, str)
  ├── Validasi mendalam (PK, FK, umur, tanggal)
  └── Simpan sebagai .parquet tervalidasi
  │
  ▼ 03-DataCleaning
  ├── Hapus orphan records
  ├── Hapus duplikat (window 30 detik)
  ├── Rekonsiliasi original_amount ← SUM(subtotal)
  ├── Capping diskon (discount_applied ≤ original_amount)
  ├── Capping outlier final_amount (P99)
  └── Simpan sebagai cleaned .parquet
  │
  ▼ 04-JoinData
  ├── LEFT JOIN transactions + users + stores = df_MasterTrans
  ├── LEFT JOIN transaction_items + menu + MasterTrans = df_Master
  ├── LEFT JOIN payment_methods
  └── Simpan df_Master_Final.parquet
  │
  ▼ 05-FeatureEngineering
  ├── Ekstrak fitur temporal (hour, month, day_name, etc.)
  ├── Buat feature flags (member_status, is_voucher_used, etc.)
  ├── Agregasi per transaksi → df_transaction_features
  ├── RFM per user → df_rfm (+ scaled features)
  ├── Matriks Apriori → df_basket_apriori
  └── Temporal split 80/20 → df_train, df_test
  │
  ▼ 06-EDA
  └── Visualisasi dan analisis bisnis
  │
  ▼ 06_Modeling_and_Evaluation
  ├── A: Baseline models (ARIMA, SARIMA, Prophet) per cabang
  ├── B: XGBoost pooled multivariate model
  ├── C: Hybrid detrending (HWR-XGB, SARIMA-XGB, Prophet-XGB)
  ├── D: Comparative evaluation + best model selection
  └── Output: df_forecast_90days.parquet untuk Voucher Engine
```

### 3.2 Transformasi kunci: original_amount

**Proses** (di `03-DataCleaning`):
1. Hitung `calculated_original_amount = SUM(subtotal)` per `transaction_id`.
2. Merge ke `df_Trans` sebagai `calculated_original_amount`.
3. Timpa `original_amount` dengan `calculated_original_amount`.
4. Hitung ulang `final_amount = original_amount - discount_applied`.
5. **Rev**: Simpan `original_amount_header` (backup nilai lama) sebelum menimpa.

**Dampak**: 2.284.725 transaksi diperbaiki. Setelah koreksi: 0 mismatch (toleransi >0,1).

### 3.3 Transformasi kunci: discount_applied (Capping)

**Aturan** (di `03-DataCleaning`):
```
IF discount_applied > original_amount:
    discount_applied = original_amount
final_amount = original_amount - discount_applied
```

**Dampak**: 784 transaksi negatif diperbaiki (penyebab: voucher SALES50 dengan diskon 50% yang tidak tepat). Setelah capping: 0 transaksi negatif.

### 3.4 Transformasi kunci: Duplikat transaction_items

**Kebijakan** (di `03-DataCleaning`):
1. Identifikasi grup duplikat berdasarkan `(transaction_id, item_id, created_at)`.
2. Dalam grup, hitung selisih waktu (`time_diff`) antar baris.
3. Hapus semua baris dalam grup yang memiliki `time_diff ≤ 30 detik`.
4. **Rev**: Pertahankan baris dengan `subtotal` maksimum dalam grup duplikat (*deterministic*).

### 3.5 Transformasi kunci: RFM

**Snapshot Date**: `MAX(created_at) + 1 day` → 2025-07-01 19:59:39 + 1 day.

**Rumus**:
- `Recency = (snapshot_date - MAX(created_at per user)).days`
- `Frequency = COUNT(transaction_id per user)`
- `Monetary = SUM(final_amount per user)`

**Repeat Customer**: `IF Frequency > 1 THEN 'Repeat Customer' ELSE 'One-Time Customer'`

**Scaled RFM (Rev)**: StandardScaler (z-score) diterapkan pada Recency, Frequency, Monetary → kolom `RFM_Scaled_*`.

### 3.6 Pemisahan Data Train/Test

**Metode**: Temporal split berdasarkan `created_at`.

| Set | Batas Waktu | Jumlah Transaksi | Persentase |
|-----|-------------|-----------------|------------|
| Train | < 2025-02-04 14:33:49 | 11.698.952 | 80% |
| Test | ≥ 2025-02-04 14:33:49 | 2.924.739 | 20% |

**Rasional**: Mencegah *data leakage* — model dilatih hanya pada data masa lalu dan diuji pada data masa depan, mensimulasikan *production setting*.

**Data yang digunakan**: `df_transaction_features` (tidak termasuk `df_basket_apriori`).

### 3.6b Pemisahan Data untuk Forecasting (Modeling)

Notebook `06_Modeling_and_Evaluation` menggunakan cutoff temporal berbeda yang disesuaikan dengan kebutuhan agregasi harian:

| Set | Batas Waktu | Jumlah Hari | Persentase |
|-----|-------------|-------------|------------|
| Train | < 2025-03-25 | ~635 hari | ~80% |
| Test | >= 2025-03-25 | ~97 hari | ~20% |

**Data yang digunakan**: `df_daily` (agregasi harian dari `df_transaction_features`, bukan data transaksi mentah).

**Fitur harian**: `total_transactions`, `total_revenue`, `avg_basket`, `lag_1`, `lag_7`, `rolling_avg_7`, `voucher_rate`, `day_of_week`, `month`.

### 3.7 Transformasi kunci: Matriks Basket Apriori

**Proses** (di `05-FeatureEngineering-Rev`):
1. Load `transaction_items_cleaned` + `menu_cleaned`.
2. Filter item dengan *global support* < 0,1% → tidak ada yang dihapus (hanya 8 item).
3. Group by `(transaction_id, item_name)` → SUM quantity.
4. Pivot ke wide format: `transaction_id` × `item_name`, diisi dengan quantity.
5. Binerisasi: > 0 → 1, else 0.
6. Hapus transaksi dengan hanya 1 item (5.559.022 transaksi).
7. Hapus transaksi > 30 item (0 transaksi).

**Hasil**: 9.064.669 transaksi × 8 item, sparsity 70,59%.

### 3.8 Lineage Kolom di df_Master_Final

| Kolom di Master | Sumber Notebook | Sumber Tabel | Transformasi |
|-----------------|----------------|-------------|--------------|
| `transaction_id` | 01-LoadData | transactions | — |
| `item_id` | 01-LoadData | transaction_items | — |
| `quantity` | 01-LoadData | transaction_items | — |
| `unit_price` | 01-LoadData | transaction_items | — |
| `subtotal` | 01-LoadData | transaction_items | quantity × unit_price (dari sumber) |
| `item_name` | 04-JoinData | menu_items | — |
| `menu_category` | 04-JoinData → 05-FE | menu_items | Di-rename dari `category_x` |
| `price` | 04-JoinData | menu_items | — |
| `is_seasonal` | 04-JoinData | menu_items | — |
| `store_id` | 01-LoadData | transactions | — |
| `payment_method_id` | 01-LoadData | transactions | — |
| `voucher_id` | 01-LoadData | transactions | Cast ke Int64 |
| `user_id` | 01-LoadData | transactions | Cast ke Int64 |
| `original_amount` | 03-DataCleaning | — | **Ditimpa** dengan SUM(subtotal) per transaksi |
| `original_amount_header` | 03-DataCleaning-Rev | transactions | **Backup** nilai original_amount sebelum rekonsiliasi |
| `discount_applied` | 03-DataCleaning | — | Di-capping: min(discount_applied, original_amount) |
| `final_amount` | 03-DataCleaning | — | original_amount - discount_applied (setelah rekonsiliasi & capping) |
| `voucher_code` | 03-DataCleaning | vouchers | Merge via left join |
| `discount_type` | 03-DataCleaning | vouchers | Merge via left join |
| `discount_value` | 03-DataCleaning | vouchers | Merge via left join |
| `valid_from` | 02-DataValidation | vouchers | Cast ke datetime64 |
| `valid_to` | 02-DataValidation | vouchers | Cast ke datetime64 |
| `calculated_discount` | 03-DataCleaning | — | Kolom audit: dihitung dari voucher rules |
| `gender` | 04-JoinData | users | Merge via left join |
| `birthdate` | 04-JoinData | users | Cast ke datetime64 |
| `registered_at` | 04-JoinData | users | Cast ke datetime64 |
| `store_name` | 04-JoinData | stores | Merge via left join |
| `street` | 04-JoinData | stores | Merge via left join |
| `postal_code` | 02-DataValidation | stores | Cast ke object |
| `city` | 04-JoinData | stores | Merge via left join |
| `state` | 04-JoinData | stores | Merge via left join |
| `latitude` | 04-JoinData | stores | — |
| `longitude` | 04-JoinData | stores | — |
| `created_at` | 02-DataValidation | transactions | Cast ke datetime64. Digabung dari `created_at_x` dan `created_at_y` |
| `method_name` | 04-JoinData | payment_methods | Merge via left join (`payment_method_id` = `method_id`) |
| `payment_category` | 04-JoinData → 05-FE | payment_methods | Di-rename dari `category_y` |

---

## 4. Kebijakan Data Governance

### 4.1 Audit Trail

- **Rev notebooks** menyediakan *audit trail* melalui kolom `original_amount_header` yang menyimpan nilai asli sebelum transformasi.
- **calculated_discount** adalah kolom audit yang memverifikasi konsistensi diskun terhadap aturan voucher, namun **tidak digunakan** dalam perhitungan hilir.
- Semua transformasi finansial didokumentasikan dan dapat dilacak (*traceable*).

### 4.2 Parameter & Thresholds Kunci

| Parameter | Nilai | Notebook | Deskripsi |
|-----------|-------|----------|-----------|
| Kardinalitas threshold | < 5% | 01-LoadData | Ambang konversi ke category |
| Toleransi rekonsiliasi | \|diff\| > 0,1 | 03-DataCleaning | Ambang mismatch header-detail |
| Toleransi validasi diskon | \|diff\| > 0,01 | 03-DataCleaning | Ambang mismatch diskon vs aturan |
| Window duplikat | ≤ 30 detik | 03-DataCleaning | Selisih waktu untuk dedup |
| Persentil capping | 99th | 03-DataCleaning | Winsorization untuk outlier |
| Batas usia wajar | 12–100 tahun | 02-DataValidation | Validasi usia saat registrasi |
| Morning | 05:00–10:59 | 05-FeatureEngineering | Periode pagi |
| Afternoon | 11:00–15:59 | 05-FeatureEngineering | Periode siang |
| Evening | 16:00–19:59 | 05-FeatureEngineering | Periode sore |
| Night | 20:00–23:59 | 05-FeatureEngineering | Periode malam |
| Repeat customer | Frequency > 1 | 05-FeatureEngineering | Ambang pelanggan berulang |
| Epsilon discount_ratio | 1e-6 | 05-FeatureEngineering | Cegah division by zero |
| Support threshold Apriori | 0,1% | 05-FE-Rev | Filter item jarang |
| Temporal split ratio | 80/20 | 05-FE-Rev | Rasio train/test |
| Z-score threshold | 3 | function.py | Ambang outlier Z-Score |
| Cutoff baseline | 2025-03-25 | 06-Modeling | Temporal split untuk forecasting (model cutoff) |
| Forecast horizon | 90 hari | 06-Modeling | Horizon prediksi ke depan |
| Holt-Winters seasonal period | 365 | 06-Modeling | Periode musiman tahunan |
| XGBoost n_estimators | 150 | 06-Modeling | Jumlah pohon boosting |
| XGBoost max_depth | 3 | 06-Modeling | Kedalaman maksimum pohon |
| XGBoost learning_rate | 0.03 | 06-Modeling | Learning rate |
| XGBoost subsample | 0.7 | 06-Modeling | Fraksi sampel per pohon |
| XGBoost reg_lambda | 10 | 06-Modeling | Regularisasi L2 |
| Min support Apriori | 0.01 | aprioriMember/NonMember | Support minimum untuk frequent itemsets |
| Min confidence Apriori | 0.1 | aprioriMember/NonMember | Confidence threshold association rules |

### 4.3 Kebijakan Preservasi Data

- **Data mentah tidak dihapus**: File CSV asli tidak dimodifikasi. Semua transformasi dilakukan pada salinan di memori.
- **Kolom audit dipertahankan**: kolom seperti `calculated_discount`, `original_amount_header` tetap disimpan di file output untuk keperluan audit.
- **Rev notebooks** memperbaiki logika tanpa mengubah kebijakan dasar — menggunakan pendekatan yang lebih deterministik dan robust.

### 4.4 Catatan Penting: Mata Uang

- Nilai moneter dalam dataset adalah dalam **Ringgit Malaysia (RM)**, bukan Indonesian Rupiah (IDR).
- Konversi ke IDR (1 RM = Rp3.500) hanya dilakukan **in-memory** pada notebook `06-EDA-Rev` untuk keperluan presentasi visual.
- File `.parquet` output tetap menyimpan nilai dalam RM.
- ATV ~RM30,36 setara dengan ~Rp106.260 — masuk akal untuk *premium coffee shop*.

---

## Appendix: Skema Tabel Ringkas

| Tabel | Baris | Kolom | Ukuran (MB) |
|-------|-------|-------|-------------|
| transactions | 14.623.691 | 9 | ~669 |
| transaction_items | 29.246.323 | 6 | ~725 |
| users | 2.196.257 | 4 | ~69 |
| stores | 10 | 8 | <1 |
| menu_items | 8 | 5 | <1 |
| vouchers | 16 | 6 | <1 |
| payment_methods | 5 | 3 | <1 |
| df_Master_Final | 26.885.688 | 40 | ~2.500+ |
| df_transaction_features | 14.623.691 | 16+ | ~500+ |
| df_rfm | 2.196.257 | 5–8 | ~70 |
| df_basket_apriori | 9.064.669 | 8 | ~804 |
| df_forecast_90days | 900 | 3 | <1 |
| df_forecast_90days_* | 900 (masing-masing) | 7 | <1 |

> **Catatan**: Tabel `df_forecast_90days_*.parquet` dihasilkan oleh notebook `09-testingXgb` untuk setiap arsitektur hybrid (HWR-XGB, SARIMA-XGB, Prophet-XGB). Tabel tunggal `df_forecast_90days.parquet` dari notebook `06_Modeling_and_Evaluation` berisi output model terbaik saja.


---

## Evaluation Metrics

The following metrics govern the validation phase across all predictive architectures in this repository. For implementation details, see individual processing notebooks.

### 1. Mean Absolute Error (MAE)
$$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |y_i - \hat{y}_i|$$
- **Context:** Applied as a scale-dependent metric to assess forecast quality directly interpretable in transaction counts.
- **Limitation:** Insensitive to variance changes as it weights all errors linearly.

### 2. Root Mean Squared Error (RMSE)
$$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (y_i - \hat{y}_i)^2}$$
- **Context:** Serves as the primary loss function indicator, penalizing large deviations quadratically to ensure model stability against outliers.

### 3. Coefficient of Determination ($R^2$)
$$R^2 = 1 - \frac{\sum_{i=1}^{n} (y_i - \hat{y}_i)^2}{\sum_{i=1}^{n} (y_i - \bar{y})^2}$$
- **Context:** Quantifies the proportion of variance explained by the model relative to a baseline mean predictor.

### 4. Mean Absolute Percentage Error (MAPE)
$$\text{MAPE} = \frac{1}{n} \sum_{i=1}^{n} \left| \frac{y_i - \hat{y}_i}{y_i} \right| \times 100\%$$
- **Context:** Used for scale-independent comparison across different operational branches.
- **Handling Constraints:** Stated errors are bounded against $y_i = 0$ cases via minor epsilon stabilization where applicable.

## Time-Series Modeling Framework & Baselines

Before integrating multivariate features via machine learning or hybrid architectures, univariate time-series models are established as lower-bound performance references. These baselines evaluate whether the target series contains exploitable temporal structures such as autocorrelation, deterministic trends, or stable seasonality.

### Univariate Model Taxonomy & Constraints

| Model | Class | Target Characteristics Captured | Structural Limitations / Failure Cases |
| :--- | :--- | :--- | :--- |
| **ARIMA** | Parametric | Autoregression ($p$), Differencing ($d$), Moving Average ($q$) | Strict wide-sense stationarity requirements; cannot capture seasonal structures natively. |
| **SARIMA** | Parametric | ARIMA components with explicit Seasonal extensions ($P,D,Q)_m$ | High hyperparameter search space optimization cost; seasonal period ($m$) must be fixed and known a priori. |
| **Prophet** | Additive | Piecewise linear/logistic trend, non-linear weekly/yearly seasonality, holiday effects | Tendency to over-smooth abrupt structural breaks; exhibits high predictive uncertainty in long-term extrapolation. |

### Architectural Integration

These univariate models establish the underlying baseline against which MLR, PCR, PLS, XGBoost, and the final Hybrid Forecasting systems are statistically cross-examined using Diebold-Mariano and Theil's U tests.

## Hybrid Detrending Framework

To address the recursive low-pass filter problem of pure XGBoost with autoregressive features, the series is decomposed into a macro component and a micro component:

$$\hat{y}_{t+h} = T_{t+h}^{\text{macro}} + \Delta_{t+h}^{\text{micro}}$$

where:
- $T^{\text{macro}}$ is forecast by a univariate time-series model (Holt-Winters, SARIMA, or Prophet).
- $\Delta^{\text{micro}}$ is predicted by XGBoost using only non-autoregressive features (day_of_week, month, voucher_rate), avoiding the recursive low-pass problem.

### Residual Definition
$$r_t = y_t - \hat{T}_t^{\text{macro}}$$
XGBoost is trained on $r_t$ using calendar features only. The final forecast is the sum of the macro extrapolation and the XGBoost residual prediction.

---

## 5. Pipeline Revision Log

The following modifications were introduced in the **Rev** notebooks relative to the original pipeline to improve determinism, auditability, and downstream modeling readiness.

### 5.1 Data Cleaning (03-DataCleaning-Rev)

| # | Fix | Description |
|---|-----|-------------|
| 1 | **Data Preservation** | `original_amount_header` is now backed up BEFORE overwriting, preserving the raw financial record. |
| 2 | **Logic Reordering** | `original_amount` correction now runs BEFORE discount validation, so `calculated_discount` uses fresh, accurate values. |
| 3 | **Deterministic Dedup** | Duplicate items now keep the row with the **maximum subtotal** instead of whichever row appears last after sorting. |
| 4 | **Band-Aid Removed** | The discount capping logic is preserved but now runs against corrected `original_amount`, making it a genuine safeguard rather than a workaround for stale data. |

### 5.2 Data Joining (04-JoinData-Rev)

| # | Fix | Description |
|---|-----|-------------|
| 1 | **Input Validation** | Explicitly verifies that `original_amount_header` exists (audit trail from DataCleaning-Rev) before proceeding. |
| 2 | **Column Cleanup Safety** | Uses explicit column name list instead of fragile `_x`/`_y` suffix matching. |
| 3 | **Validation Enhancement** | Financial audit now also checks that `original_amount_header` is preserved with expected values. |

### 5.3 Feature Engineering (05-FeatureEngineering-Rev)

| # | Fix | Description |
|---|-----|-------------|
| 1 | **Deterministic Aggregation** | Replaced `.first()` with `.max()` for all transaction-level fields. `.first()` depends on DataFrame row order (which can change with Parquet reads); `.max()` is fully deterministic. |
| 2 | **K-Means Readiness** | Added `RFM_Scaled` columns (StandardScaler) so Euclidean distance does not let Monetary dominate Recency/Frequency. |
| 3 | **XGBoost Readiness** | Added a time-based train/test split framework (80/20 temporal cutoff) to prevent look-ahead data leakage. |
| 4 | **Modeling-Friendly Encoding** | Added `is_weekend_bool` (0/1) and `is_voucher_used_bool` (0/1) for direct modeling consumption. |
| 5 | **Input Validation** | Checks for `original_amount_header` from the audit trail. |

### Detailed Rationale

**Fix #1 -- Deterministic Aggregation:**
The original code used `.first()` for 15/16 aggregation fields. `.first()` picks the first row encountered in each group, which depends on the arbitrary row order from Parquet reads. If data is shuffled or read differently, `.first()` can return different results. The fix replaces it with `.max()`: since all transaction-level fields are identical for items within the same transaction, `.max()` always returns the same value regardless of row order. Additionally, `basket_size` (sum of quantities) and `item_count` (unique items per transaction) are added as new features.

**Fix #2 -- K-Means Readiness (RFM Scaling):**
Raw RFM features operate on vastly different scales: Recency spans 0--730 days, Frequency follows a power-law distribution (1--40+ transactions), and Monetary ranges from Rp0 to Rp1,348+. K-Means clustering relies on Euclidean distance; without scaling, the Monetary dimension dominates distance calculations, rendering Recency and Frequency nearly irrelevant to cluster assignment. StandardScaler (z-score normalization) is applied to produce `RFM_Scaled_*` columns. A MinMaxScaler alternative is included as a commented option.

**Fix #3 -- Temporal Train/Test Split for XGBoost:**
The original pipeline lacked a mechanism to prevent data leakage in forecasting contexts. Training XGBoost on all available data -- including future transactions -- would allow the model to learn patterns from data that would not exist in a production setting. The fix creates a strict temporal split: the first 80% of the timeline is used for training, the remaining 20% for testing, based on `created_at` (transaction date). The cutoff date is stored in the Parquet file metadata for downstream consumption.
