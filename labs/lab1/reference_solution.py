"""
Reference solution for Lab 1, following the notebook's section order exactly
(including the intentional "leakage trap": impute/encode/outlier-handle on the
whole dataframe in sections 3-5, split in section 6, scale properly in
section 7). Used to derive real, verified constants for preprocessing_tests.py
-- never shipped to students.
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

pd.set_option("display.width", 120)

df_raw = pd.read_csv("employee_data.csv")
print("=== raw shape ===", df_raw.shape)

df = df_raw.copy()

# ---- Section 3: missing values (median impute, on whole df -- the trap) ----
exp_median = df["YearsExperience"].median()
perf_median = df["PerformanceScore"].median()
print("\n=== medians used for imputation ===")
print("YearsExperience median:", exp_median)
print("PerformanceScore median:", perf_median)

df["YearsExperience"] = df["YearsExperience"].fillna(exp_median)
df["PerformanceScore"] = df["PerformanceScore"].fillna(perf_median)
assert df[["YearsExperience", "PerformanceScore"]].isnull().sum().sum() == 0

# ---- Section 4: categorical encoding ----
cat_cols = ["Department", "EducationLevel", "RemoteStatus"]
df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=True)
print("\n=== columns after encoding ===")
print(list(df_encoded.columns))
print("n columns after encoding:", df_encoded.shape[1])

# ---- Section 5: outliers on Salary (IQR rule, on whole df -- the trap) ----
q1 = df_encoded["Salary"].quantile(0.25)
q3 = df_encoded["Salary"].quantile(0.75)
iqr = q3 - q1
lower = q1 - 1.5 * iqr
upper = q3 + 1.5 * iqr
print("\n=== IQR bounds for Salary ===")
print("Q1:", q1, "Q3:", q3, "IQR:", iqr)
print("lower bound:", lower, "upper bound:", upper)

before_rows = len(df_encoded)
df_clean = df_encoded[(df_encoded["Salary"] >= lower) & (df_encoded["Salary"] <= upper)].reset_index(drop=True)
after_rows = len(df_clean)
print("rows before outlier removal:", before_rows, "-> after:", after_rows, "removed:", before_rows - after_rows)

# ---- Section 6: leakage-safe split (on the cleaned/encoded data) ----
feature_cols = [c for c in df_clean.columns if c not in ("Salary", "Attrition")]
X = df_clean[feature_cols].to_numpy()
y = df_clean["Salary"].to_numpy()

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=1)
print("\n=== split shapes ===")
print("X_train:", X_train.shape, "X_test:", X_test.shape)
print("sum(X_test) check value:", np.sum(X_test))
print("sum(y_test) check value:", np.sum(y_test))

# ---- Section 7: scaling (fit on train only, transform both) ----
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
print("\n=== scaler stats (fit on train only) ===")
print("train mean (should be ~0):", np.round(X_train_scaled.mean(axis=0), 6))
print("train std  (should be ~1):", np.round(X_train_scaled.std(axis=0), 6))
print("test mean (should NOT be exactly 0):", np.round(X_test_scaled.mean(axis=0), 4))

# ---- Section 8: payoff -- dirty vs clean model ----
# Dirty: raw data, numeric-only columns, NaNs dropped just to make .fit() runnable,
# NO outlier removal, NO scaling -- the "naive beginner" baseline.
df_dirty = df_raw.copy()
df_dirty_encoded = pd.get_dummies(df_dirty, columns=cat_cols, drop_first=True)
df_dirty_encoded = df_dirty_encoded.dropna()
feature_cols_dirty = [c for c in df_dirty_encoded.columns if c not in ("Salary", "Attrition")]
Xd = df_dirty_encoded[feature_cols_dirty].to_numpy()
yd = df_dirty_encoded["Salary"].to_numpy()
Xd_train, Xd_test, yd_train, yd_test = train_test_split(Xd, yd, test_size=0.2, random_state=1)

dirty_model = LinearRegression().fit(Xd_train, yd_train)
dirty_r2 = r2_score(yd_test, dirty_model.predict(Xd_test))

clean_model = LinearRegression().fit(X_train_scaled, y_train)
clean_r2 = r2_score(y_test, clean_model.predict(X_test_scaled))

print("\n=== PAYOFF ===")
print("Dirty-data R^2:", dirty_r2)
print("Clean-data R^2:", clean_r2)
print("Improvement:", clean_r2 - dirty_r2)
