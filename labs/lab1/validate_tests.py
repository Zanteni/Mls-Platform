import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from preprocessing_tests import *

df_raw = pd.read_csv("employee_data.csv")
df = df_raw.copy()

exp_median = df["YearsExperience"].median()
perf_median = df["PerformanceScore"].median()
df["YearsExperience"] = df["YearsExperience"].fillna(exp_median)
df["PerformanceScore"] = df["PerformanceScore"].fillna(perf_median)
missing_values_test(df, exp_median, perf_median)

cat_cols = ["Department", "EducationLevel", "RemoteStatus"]
df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=True)
encoding_test(df_encoded)

q1 = df_encoded["Salary"].quantile(0.25)
q3 = df_encoded["Salary"].quantile(0.75)
iqr = q3 - q1
lower = q1 - 1.5 * iqr
upper = q3 + 1.5 * iqr
df_clean = df_encoded[(df_encoded["Salary"] >= lower) & (df_encoded["Salary"] <= upper)].reset_index(drop=True)
outlier_test(df_clean, lower, upper)

feature_cols = [c for c in df_clean.columns if c not in ("Salary", "Attrition")]
X = df_clean[feature_cols].to_numpy()
y = df_clean["Salary"].to_numpy()
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=1)
split_test(X_train, X_test, y_train, y_test)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
scaling_test(X_train_scaled, X_test_scaled)

print("ALL LAB 1 TESTS VALIDATED AGAINST REFERENCE SOLUTION")
