"""
Reference solution for Lab 2. Builds the corrected (leakage-safe) setup pipeline
that both notebooks share as "given" cells, then trains both models to derive
real constants for the test files. Never shipped to students.
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import r2_score, mean_squared_error, accuracy_score, confusion_matrix, precision_score, recall_score

# ---------------- Shared setup (same in both notebooks, given/ungraded) ----------------

df = pd.read_csv("employee_data.csv")

cat_cols = ["Department", "EducationLevel", "RemoteStatus"]
df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=True)  # safe pre-split: structural, not statistical
df_encoded["Attrition"] = (df_encoded["Attrition"] == "Yes").astype(int)

feature_cols = [c for c in df_encoded.columns if c not in ("Salary", "Attrition")]
X = df_encoded[feature_cols].to_numpy(dtype=float)
y_salary = df_encoded["Salary"].to_numpy()
y_attrition = df_encoded["Attrition"].to_numpy()

# split FIRST, on the raw (still has NaNs, still has outliers) data
X_train, X_test, y_salary_train, y_salary_test, y_attrition_train, y_attrition_test = train_test_split(
    X, y_salary, y_attrition, test_size=0.2, random_state=1
)
print("Initial split:", X_train.shape, X_test.shape)

exp_idx = feature_cols.index("YearsExperience")
perf_idx = feature_cols.index("PerformanceScore")

exp_median = np.nanmedian(X_train[:, exp_idx])
perf_median = np.nanmedian(X_train[:, perf_idx])
print("Train-only medians:", exp_median, perf_median)

X_train[np.isnan(X_train[:, exp_idx]), exp_idx] = exp_median
X_test[np.isnan(X_test[:, exp_idx]), exp_idx] = exp_median
X_train[np.isnan(X_train[:, perf_idx]), perf_idx] = perf_median
X_test[np.isnan(X_test[:, perf_idx]), perf_idx] = perf_median
assert not np.isnan(X_train).any() and not np.isnan(X_test).any()

# outlier bounds from TRAIN salary only
q1, q3 = np.percentile(y_salary_train, [25, 75])
iqr = q3 - q1
lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
print("Train-derived IQR bounds:", lower, upper)

train_mask = (y_salary_train >= lower) & (y_salary_train <= upper)
test_mask = (y_salary_test >= lower) & (y_salary_test <= upper)

X_train, y_salary_train, y_attrition_train = X_train[train_mask], y_salary_train[train_mask], y_attrition_train[train_mask]
X_test, y_salary_test, y_attrition_test = X_test[test_mask], y_salary_test[test_mask], y_attrition_test[test_mask]
print("After outlier filtering:", X_train.shape, X_test.shape)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print("\nFinal shapes: X_train", X_train_scaled.shape, "X_test", X_test_scaled.shape)
print("y_attrition_train balance:", np.mean(y_attrition_train))
print("sum(X_test_scaled) check:", np.sum(X_test_scaled))
print("sum(y_salary_test) check:", np.sum(y_salary_test))
print("sum(y_attrition_test) check:", np.sum(y_attrition_test))

# ---------------- scikit-learn models (for sklearn notebook constants) ----------------

lin_reg = LinearRegression().fit(X_train_scaled, y_salary_train)
salary_pred = lin_reg.predict(X_test_scaled)
lin_r2 = r2_score(y_salary_test, salary_pred)
lin_mse = mean_squared_error(y_salary_test, salary_pred)
print("\nsklearn LinearRegression -> R2:", lin_r2, " MSE:", lin_mse)

log_reg = LogisticRegression().fit(X_train_scaled, y_attrition_train)
attrition_pred = log_reg.predict(X_test_scaled)
acc = accuracy_score(y_attrition_test, attrition_pred)
cm = confusion_matrix(y_attrition_test, attrition_pred)
prec = precision_score(y_attrition_test, attrition_pred)
rec = recall_score(y_attrition_test, attrition_pred)
print("sklearn LogisticRegression -> accuracy:", acc)
print("confusion matrix:\n", cm)
print("precision:", prec, "recall:", rec)

# ---------------- from-scratch gradient descent (for scratch notebook, sanity-run) ----------------

def predict_linear(X, w, b):
    return X @ w + b

def compute_cost_linear(X, y, w, b):
    m = X.shape[0]
    f_wb = predict_linear(X, w, b)
    return (1 / (2 * m)) * np.sum((f_wb - y) ** 2)

def compute_gradient_linear(X, y, w, b):
    m = X.shape[0]
    error = predict_linear(X, w, b) - y
    dj_dw = (1 / m) * (X.T @ error)
    dj_db = (1 / m) * np.sum(error)
    return dj_dw, dj_db

def gradient_descent(X, y, w_in, b_in, cost_function, gradient_function, alpha, num_iters):
    w, b = w_in.copy(), b_in
    J_history = []
    for i in range(num_iters):
        dj_dw, dj_db = gradient_function(X, y, w, b)
        w = w - alpha * dj_dw
        b = b - alpha * dj_db
        J_history.append(cost_function(X, y, w, b))
    return w, b, J_history

w0 = np.zeros(X_train_scaled.shape[1])
w_final, b_final, J_hist = gradient_descent(
    X_train_scaled, y_salary_train, w0, 0.0, compute_cost_linear, compute_gradient_linear, alpha=0.1, num_iters=1000
)
scratch_r2 = r2_score(y_salary_test, predict_linear(X_test_scaled, w_final, b_final))
print("\nScratch linear regression -> R2 (alpha=0.1, iters=1000):", scratch_r2)
print("Cost decreased:", J_hist[0], "->", J_hist[-1])

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

def predict_logistic(X, w, b):
    return sigmoid(X @ w + b)

def compute_cost_logistic(X, y, w, b):
    m = X.shape[0]
    eps = 1e-12
    f_wb = predict_logistic(X, w, b)
    return -(1 / m) * np.sum(y * np.log(f_wb + eps) + (1 - y) * np.log(1 - f_wb + eps))

def compute_gradient_logistic(X, y, w, b):
    m = X.shape[0]
    error = predict_logistic(X, w, b) - y
    dj_dw = (1 / m) * (X.T @ error)
    dj_db = (1 / m) * np.sum(error)
    return dj_dw, dj_db

w0b = np.zeros(X_train_scaled.shape[1])
w_final_log, b_final_log, J_hist_log = gradient_descent(
    X_train_scaled, y_attrition_train, w0b, 0.0, compute_cost_logistic, compute_gradient_logistic, alpha=0.5, num_iters=1000
)
scratch_pred = (predict_logistic(X_test_scaled, w_final_log, b_final_log) >= 0.5).astype(int)
scratch_acc = accuracy_score(y_attrition_test, scratch_pred)
print("\nScratch logistic regression -> accuracy (alpha=0.5, iters=1000):", scratch_acc)
print("Cost decreased:", J_hist_log[0], "->", J_hist_log[-1])
