"""
Test functions for the Lab 2 sklearn notebook (lin_log_sklearn.ipynb).
Do not modify this file - it is used to verify your implementation.
"""
import numpy as np

GREEN = "\033[92m"
RESET = "\033[0m"


def split_test(X_train, X_test, y_salary_train, y_salary_test, y_attrition_train, y_attrition_test):
    assert X_train.shape == (382, 8), f"Expected X_train.shape=(382, 8), got {X_train.shape}"
    assert X_test.shape == (97, 8), f"Expected X_test.shape=(97, 8), got {X_test.shape}"
    assert np.isclose(np.sum(X_test), -10.61, atol=1.0), \
        "X_test does not match expected values - check the setup cells were run in order"
    assert np.isclose(np.sum(y_salary_test), 6762825.36, atol=10.0), "y_salary_test does not match expected values"
    assert int(np.sum(y_attrition_test)) == 31, f"Expected sum(y_attrition_test)=31, got {int(np.sum(y_attrition_test))}"
    print(f"{GREEN}All tests passed!{RESET}")


def linear_model_test(lin_reg, X_test, y_test):
    from sklearn.metrics import r2_score
    preds = lin_reg.predict(X_test)
    r2 = r2_score(y_test, preds)
    assert r2 > 0.75, f"R² is {r2:.3f} - expected something close to 0.81. Check the model was fit on the scaled training data."
    print(f"{GREEN}All tests passed!{RESET}")


def logistic_model_test(log_reg, X_test, y_test):
    from sklearn.metrics import accuracy_score
    preds = log_reg.predict(X_test)
    acc = accuracy_score(y_test, preds)
    # 0.68 is the majority-class baseline on this test set
    assert acc > 0.68, f"Accuracy is {acc:.3f}, which does not clearly beat the 0.68 majority-class baseline."
    print(f"{GREEN}All tests passed!{RESET}")
