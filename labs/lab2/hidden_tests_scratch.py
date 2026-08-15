"""
Test functions for the Lab 2 scratch notebook (lin_log_scratch.ipynb).
Do not modify this file - it is used to verify your implementation.
"""
import numpy as np

GREEN = "\033[92m"
RESET = "\033[0m"

# Shared toy inputs, independent of the real dataset
X_toy = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
y_toy_reg = np.array([5.0, 11.0, 17.0])
y_toy_clf = np.array([0, 0, 1])
w_toy = np.array([1.0, 2.0])
b_toy = 0.5


def split_test(X_train, X_test, y_salary_train, y_salary_test, y_attrition_train, y_attrition_test):
    assert X_train.shape == (382, 8), f"Expected X_train.shape=(382, 8), got {X_train.shape}"
    assert X_test.shape == (97, 8), f"Expected X_test.shape=(97, 8), got {X_test.shape}"
    assert np.isclose(np.sum(X_test), -10.61, atol=1.0), \
        "X_test does not match expected values - check the setup cells were run in order"
    assert np.isclose(np.sum(y_salary_test), 6762825.36, atol=10.0), "y_salary_test does not match expected values"
    assert int(np.sum(y_attrition_test)) == 31, f"Expected sum(y_attrition_test)=31, got {int(np.sum(y_attrition_test))}"
    print(f"{GREEN}All tests passed!{RESET}")


def predict_linear_test(predict_linear):
    result = predict_linear(X_toy, w_toy, b_toy)
    expected = np.array([5.5, 11.5, 17.5])
    assert np.allclose(result, expected), f"Expected {expected}, got {result}"
    print(f"{GREEN}All tests passed!{RESET}")


def compute_cost_linear_test(compute_cost_linear):
    result = compute_cost_linear(X_toy, y_toy_reg, w_toy, b_toy)
    assert np.isclose(result, 0.125), f"Expected 0.125, got {result}"
    print(f"{GREEN}All tests passed!{RESET}")


def compute_gradient_linear_test(compute_gradient_linear):
    dj_dw, dj_db = compute_gradient_linear(X_toy, y_toy_reg, w_toy, b_toy)
    assert np.allclose(dj_dw, [1.5, 2.0]), f"dj_dw expected [1.5, 2.0], got {dj_dw}"
    assert np.isclose(dj_db, 0.5), f"dj_db expected 0.5, got {dj_db}"
    print(f"{GREEN}All tests passed!{RESET}")


def gradient_descent_test(gradient_descent, compute_cost_linear, compute_gradient_linear):
    w0 = np.zeros(2)
    w_f, b_f, J_hist = gradient_descent(
        X_toy, y_toy_reg, w0, 0.0, compute_cost_linear, compute_gradient_linear, alpha=0.05, num_iters=50
    )
    assert np.allclose(w_f, [1.32595615, 1.67017817], atol=1e-4), f"w_final does not match expected, got {w_f}"
    assert np.isclose(b_f, 0.3442220195, atol=1e-4), f"b_final does not match expected, got {b_f}"
    assert J_hist[0] > J_hist[-1], "Cost should decrease over iterations - it did not"
    assert np.isclose(J_hist[-1], 2.385346944394606e-05, atol=1e-4), f"final cost does not match expected, got {J_hist[-1]}"
    print(f"{GREEN}All tests passed!{RESET}")


def train_linear_test(w_final, b_final, J_history, r2_test):
    assert len(J_history) > 1, "J_history looks empty - did gradient_descent run?"
    assert J_history[0] > J_history[-1], \
        "Cost did not decrease - check your alpha isn't too large, or your functions are wired correctly"
    assert r2_test > 0.5, \
        f"R² on the test set is {r2_test:.3f}, which is low for this dataset - try more iterations or a different alpha"
    print(f"{GREEN}All tests passed!{RESET}")


def sigmoid_test(sigmoid):
    result = sigmoid(np.array([-1.0, 0.0, 1.0, 2.0]))
    expected = np.array([0.26894142, 0.5, 0.73105858, 0.88079708])
    assert np.allclose(result, expected, atol=1e-6), f"Expected {expected}, got {result}"
    print(f"{GREEN}All tests passed!{RESET}")


def predict_logistic_test(predict_logistic):
    result = predict_logistic(X_toy, w_toy, b_toy)
    expected = np.array([0.99592986, 0.99998987, 0.99999997])
    assert np.allclose(result, expected, atol=1e-6), f"Expected {expected}, got {result}"
    print(f"{GREEN}All tests passed!{RESET}")


def compute_cost_logistic_test(compute_cost_logistic):
    result = compute_cost_logistic(X_toy, y_toy_clf, w_toy, b_toy)
    assert np.isclose(result, 5.668029499821487, atol=1e-4), f"Expected ~5.668, got {result}"
    print(f"{GREEN}All tests passed!{RESET}")


def compute_gradient_logistic_test(compute_gradient_logistic):
    dj_dw, dj_db = compute_gradient_logistic(X_toy, y_toy_clf, w_toy, b_toy)
    assert np.allclose(dj_dw, [1.33196645, 1.99727302], atol=1e-4), f"dj_dw does not match expected, got {dj_dw}"
    assert np.isclose(dj_db, 0.665306569061044, atol=1e-4), f"dj_db does not match expected, got {dj_db}"
    print(f"{GREEN}All tests passed!{RESET}")


def train_logistic_test(w_final, b_final, J_history, accuracy_test):
    assert len(J_history) > 1, "J_history looks empty - did gradient_descent run?"
    assert J_history[0] > J_history[-1], \
        "Cost did not decrease - check your alpha isn't too large, or your functions are wired correctly"
    # 0.68 is the majority-class baseline on this test set - beating it means the model learned something real
    assert accuracy_test > 0.68, \
        f"Accuracy on the test set is {accuracy_test:.3f}, which does not clearly beat the 0.68 majority-class baseline - try more iterations or a different alpha"
    print(f"{GREEN}All tests passed!{RESET}")
