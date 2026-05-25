import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import warnings
warnings.filterwarnings('ignore')
class CleaningData:
    def __init__(self, data):
        self.data = data
    def Duplicate(self, column_name):
        # ---------------------------------------------------------
        # 1. CEK DUPLIKAT
        # ---------------------------------------------------------
        duplicate_count = self.data[column_name].duplicated().sum()
        return duplicate_count
    def BoxPlot(self, column_name, Target = None):
        # ---------------------------------------------------------
        # 3. CEK BOX PLOT
        # ---------------------------------------------------------
        if Target is not None:
            plot_target = Target
        else:
            plot_target = self.data[column_name]
        plot_target.plot.box(vert=False)
        plt.show()
    def HistPlot(self, column_name, Target = None):
        # ---------------------------------------------------------
        # 4. CEK HISTOGRAM
        # ---------------------------------------------------------
        if Target is not None:
            hist_target = Target
        else:
            hist_target = self.data[column_name]
        hist_target.hist(bins=100)
        plt.show()
    def iqr(self, column_name):
        # ---------------------------------------------------------
        # 1. METODE IQR
        # ---------------------------------------------------------
        data = self.data[column_name].dropna()
        Q1 = data.quantile(0.25)
        Q3 = data.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        iqr_data = data[(data >= lower_bound) & (data <= upper_bound)]
        # Hitung jumlah data yang dianggap outlier
        outliers = self.data[(self.data[column_name] < lower_bound) | (self.data[column_name] > upper_bound)]
        iqr_loss = len(outliers)
        original_count = len(self.data) 
        return iqr_loss, original_count, iqr_data

    def capping(self, column_name):
        # ---------------------------------------------------------
        # 2. METODE CAPPING (WINSORIZATION 99th PERCENTILE)
        # ---------------------------------------------------------
        cap_value = self.data[column_name].quantile(0.99)
        capped_data = np.where(self.data[column_name] > cap_value, cap_value, self.data[column_name])
        capped_data = pd.Series(capped_data, index=self.data.index) 
        capped_skew = capped_data.skew()
        capped_affected = (self.data[column_name] > cap_value).sum()
        return capped_skew, capped_affected, capped_data

    def log_transform(self, column_name):
        # ---------------------------------------------------------
        # 3. METODE LOG TRANSFORM
        # ---------------------------------------------------------
        log_data = np.log1p(self.data[column_name])  # log1p untuk menghindari log(0)
        log_skew = log_data.skew()
        return log_skew, log_data
    
    def z_score_method(self, column_name, threshold=3):
        # ---------------------------------------------------------
        # METODE Z-SCORE
        # ---------------------------------------------------------
        data_col = self.data[column_name].dropna()
        
        # Hitung Z-Score
        z_scores = np.abs(stats.zscore(data_col))
        
        # Filter data: ambil yang Z-score nya kurang dari threshold (biasanya 3)
        z_data_clean = data_col[z_scores < threshold]
        
        # Identifikasi outlier
        outliers = data_col[z_scores >= threshold]
        
        z_loss = len(outliers)
        original_count = len(self.data)
        
        return z_loss, original_count, z_data_clean

def optimize_numeric_data(df):

    for col in df.columns:

        # FLOAT
        if pd.api.types.is_float_dtype(df[col]):

            df[col] = pd.to_numeric(
                df[col],
                downcast='float'
            )

        # INTEGER
        elif pd.api.types.is_integer_dtype(df[col]):

            # Nullable integer
            if 'Int' in str(df[col].dtype):

                df[col] = df[col].astype('Int32')

            else:

                df[col] = pd.to_numeric(
                    df[col],
                    downcast='integer'
                )

    return df


def optimize_object_data(df, threshold=0.05):

    for col in df.columns:

        if df[col].dtype == 'object':

            num_unique = df[col].nunique(dropna=False)
            total = len(df[col])

            ratio = num_unique / total

            # Low cardinality only
            if ratio < threshold:

                df[col] = (
                    df[col]
                    .astype('category')
                )

    return df