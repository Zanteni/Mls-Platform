"""
Test functions for the Employee Salary & Attrition preprocessing lab.

Do not modify this file - it is used to verify your implementation.
"""

import numpy as np
import pandas as pd

GREEN = "\033[92m"
RESET = "\033[0m"


def missing_values_test(df, exp_median_used, perf_median_used):
    assert df["YearsExperience"].isnull().sum() == 0, \
        "YearsExperience still has missing values"
    assert df["PerformanceScore"].isnull().sum() == 0, \
        "PerformanceScore still has missing values"

    assert np.isclose(exp_median_used, 5.9), \
        f"Median used for YearsExperience looks wrong. Expected 5.9, got {exp_median_used}"
    assert np.isclose(perf_median_used, 3.0), \
        f"Median used for PerformanceScore looks wrong. Expected 3.0, got {perf_median_used}"

    print(f"{GREEN}All tests passed!{RESET}")


def encoding_test(df_encoded):
    expected_cols = {
        "Department_HR", "Department_Marketing", "Department_Sales",
        "EducationLevel_Master", "EducationLevel_PhD",
        "RemoteStatus_Remote",
    }
    assert expected_cols.issubset(set(df_encoded.columns)), \
        f"Missing expected dummy columns. Expected these to exist: {expected_cols}"

    dropped_first = {"Department_Engineering", "EducationLevel_Bachelor", "RemoteStatus_Onsite"}
    assert dropped_first.isdisjoint(set(df_encoded.columns)), \
        "It looks like drop_first=True was not used - the reference category columns are still present"

    remaining_object_cols = df_encoded.drop(columns=["Attrition"], errors="ignore").select_dtypes(include="object").columns.tolist()
    assert len(remaining_object_cols) == 0, \
        f"These columns are still non-numeric after encoding: {remaining_object_cols}"

    print(f"{GREEN}All tests passed!{RESET}")


def outlier_test(df_clean, lower_bound, upper_bound):
    assert np.isclose(lower_bound, 39050.315, atol=1.0), \
        f"lower_bound does not match the expected IQR bound, got {lower_bound}"
    assert np.isclose(upper_bound, 100528.875, atol=1.0), \
        f"upper_bound does not match the expected IQR bound, got {upper_bound}"

    assert len(df_clean) == 479, \
        f"Expected 479 rows after outlier removal, got {len(df_clean)}"
    assert df_clean["Salary"].max() <= upper_bound, \
        "Some rows above the upper bound are still present"
    assert df_clean["Salary"].min() >= lower_bound, \
        "Some rows below the lower bound are still present"

    print(f"{GREEN}All tests passed!{RESET}")


def split_test(X_train, X_test, y_train, y_test):
    assert X_train is not None and X_test is not None, \
        "X_train / X_test is None - call train_test_split first"

    assert X_train.shape == (383, 8), f"Expected X_train.shape=(383, 8), got {X_train.shape}"
    assert X_test.shape == (96, 8), f"Expected X_test.shape=(96, 8), got {X_test.shape}"
    assert len(y_train) == 383 and len(y_test) == 96, \
        "y_train / y_test have the wrong length - did you split with test_size=0.2, random_state=1?"

    assert np.isclose(np.sum(X_test), 1116.6, atol=1.0), \
        "X_test does not match the expected values - did you use random_state=1, and split the cleaned/encoded data?"
    assert np.isclose(np.sum(y_test), 6836812.73, atol=10.0), \
        "y_test does not match the expected values - did you split the cleaned data (post outlier removal)?"

    print(f"{GREEN}All tests passed!{RESET}")


def scaling_test(X_train_scaled, X_test_scaled):
    assert X_train_scaled is not None and X_test_scaled is not None, \
        "X_train_scaled / X_test_scaled is None - fit and transform first"

    train_mean = np.mean(X_train_scaled, axis=0)
    train_std = np.std(X_train_scaled, axis=0)
    assert np.allclose(train_mean, 0, atol=1e-6), \
        f"Train set mean should be ~0 after scaling, got {train_mean}"
    assert np.allclose(train_std, 1, atol=1e-6), \
        f"Train set std should be ~1 after scaling, got {train_std}"

    test_mean = np.mean(X_test_scaled, axis=0)
    assert not np.allclose(test_mean, 0, atol=1e-6), \
        ("Test set mean is exactly 0 - this usually means the scaler was fit on the test set "
         "(or on the full dataset) instead of on the training set only")

    print(f"{GREEN}All tests passed!{RESET}")
