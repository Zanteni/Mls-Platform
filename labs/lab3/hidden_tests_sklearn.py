"""
Hidden tests for Lab 3 — SVM with Scikit-Learn.

This file must NEVER be included in student repositories.

The tests verify behavior, not the student's exact implementation.
"""

import numpy as np

from sklearn.svm import SVC


# ============================================================
# Helpers
# ============================================================

def _passed():
    print("\033[92mAll tests passed!\033[0m")


def _fail(message):
    raise AssertionError(message)


# ============================================================
# Shared deterministic test data
# ============================================================

def _test_data(n_features):
    """
    Create deterministic binary classification data with
    the same number of features as the submitted model.
    """

    X_train = np.zeros((6, n_features), dtype=float)
    X_test = np.zeros((5, n_features), dtype=float)

    # Put the useful signal in the first two features.
    X_train[:, :2] = np.array([
        [-2.0, -2.0],
        [-1.0, -1.0],
        [-2.0, -1.0],
        [1.0, 1.0],
        [2.0, 1.0],
        [1.0, 2.0],
    ])

    X_test[:, :2] = np.array([
        [-2.0, -1.0],
        [-1.0, 2.0],
        [0.0, 0.0],
        [1.0, 2.0],
        [2.0, 1.0],
    ])

    y_train = np.array([
        -1,
        -1,
        -1,
        1,
        1,
        1,
    ])

    y_test = np.array([
        -1,
        1,
        1,
        1,
        1,
    ])

    return X_train, X_test, y_train, y_test

# ============================================================
# 1. Train/test split
# ============================================================

def split_test(X_train, X_test, y_train, y_test):
    """
    Verify the train/test split has the expected structure.
    """

    if not isinstance(X_train, np.ndarray):
        _fail("X_train must be a NumPy array.")

    if not isinstance(X_test, np.ndarray):
        _fail("X_test must be a NumPy array.")

    if not isinstance(y_train, np.ndarray):
        _fail("y_train must be a NumPy array.")

    if not isinstance(y_test, np.ndarray):
        _fail("y_test must be a NumPy array.")

    if X_train.ndim != 2:
        _fail(
            f"X_train must be 2-dimensional. "
            f"Got shape {X_train.shape}."
        )

    if X_test.ndim != 2:
        _fail(
            f"X_test must be 2-dimensional. "
            f"Got shape {X_test.shape}."
        )

    if y_train.ndim != 1:
        _fail(
            f"y_train must be 1-dimensional. "
            f"Got shape {y_train.shape}."
        )

    if y_test.ndim != 1:
        _fail(
            f"y_test must be 1-dimensional. "
            f"Got shape {y_test.shape}."
        )

    if X_train.shape[0] != len(y_train):
        _fail("X_train and y_train have inconsistent sample counts.")

    if X_test.shape[0] != len(y_test):
        _fail("X_test and y_test have inconsistent sample counts.")

    if X_train.shape[1] != X_test.shape[1]:
        _fail(
            "X_train and X_test must have the same number of features."
        )

    if X_train.shape[0] == 0 or X_test.shape[0] == 0:
        _fail("Train and test sets must not be empty.")

    train_labels = set(np.unique(y_train))
    test_labels = set(np.unique(y_test))

    if not train_labels.issubset({-1, 1}):
        _fail(
            f"y_train must contain only -1 and +1. "
            f"Got {train_labels}."
        )

    if not test_labels.issubset({-1, 1}):
        _fail(
            f"y_test must contain only -1 and +1. "
            f"Got {test_labels}."
        )

    _passed()


# ============================================================
# 2. Linear SVC
# ============================================================

def linear_svc_test(linear_svc):
    """
    Verify that linear_svc is a fitted linear SVC.
    """

    if not isinstance(linear_svc, SVC):
        _fail(
            "linear_svc must be an instance of sklearn.svm.SVC."
        )

    if linear_svc.kernel != "linear":
        _fail(
            f"linear_svc must use kernel='linear'. "
            f"Got {linear_svc.kernel!r}."
        )

    if not hasattr(linear_svc, "support_"):
        _fail(
            "linear_svc does not appear to be fitted."
        )

    if not hasattr(linear_svc, "support_vectors_"):
        _fail(
            "linear_svc is missing support_vectors_."
        )

    X_train, X_test, y_train, y_test = _test_data(
        linear_svc.n_features_in_
    )

    predictions = linear_svc.predict(X_test)

    if not isinstance(predictions, np.ndarray):
        _fail(
            "linear_svc.predict() must return a NumPy array."
        )

    if predictions.shape != y_test.shape:
        _fail(
            f"Prediction shape {predictions.shape} does not match "
            f"expected shape {y_test.shape}."
        )

    if not set(np.unique(predictions)).issubset({-1, 1}):
        _fail(
            "linear_svc predictions must contain only -1 and +1."
        )

    scores = linear_svc.decision_function(X_test)

    if not isinstance(scores, np.ndarray):
        _fail(
            "linear_svc.decision_function() must return a NumPy array."
        )

    if scores.shape != (len(X_test),):
        _fail(
            f"Decision scores have wrong shape: {scores.shape}."
        )

    if not np.all(np.isfinite(scores)):
        _fail(
            "linear_svc decision scores contain NaN or infinity."
        )

    _passed()


# ============================================================
# 3. Polynomial SVC
# ============================================================

def polynomial_svc_test(poly_svc):
    """
    Verify that poly_svc is a fitted polynomial SVC.
    """

    if not isinstance(poly_svc, SVC):
        _fail(
            "poly_svc must be an instance of sklearn.svm.SVC."
        )

    if poly_svc.kernel != "poly":
        _fail(
            f"poly_svc must use kernel='poly'. "
            f"Got {poly_svc.kernel!r}."
        )

    if not hasattr(poly_svc, "support_"):
        _fail(
            "poly_svc does not appear to be fitted."
        )

    if not hasattr(poly_svc, "support_vectors_"):
        _fail(
            "poly_svc is missing support_vectors_."
        )

    X_train, X_test, y_train, y_test = _test_data(
        poly_svc.n_features_in_
    )

    predictions = poly_svc.predict(X_test)

    if not isinstance(predictions, np.ndarray):
        _fail(
            "poly_svc.predict() must return a NumPy array."
        )

    if predictions.shape != y_test.shape:
        _fail(
            f"Prediction shape {predictions.shape} does not match "
            f"expected shape {y_test.shape}."
        )

    if not set(np.unique(predictions)).issubset({-1, 1}):
        _fail(
            "poly_svc predictions must contain only -1 and +1."
        )

    _passed()


# ============================================================
# 4. RBF SVC
# ============================================================

def rbf_svc_test(rbf_svc):
    """
    Verify that rbf_svc is a fitted RBF SVC.
    """

    if not isinstance(rbf_svc, SVC):
        _fail(
            "rbf_svc must be an instance of sklearn.svm.SVC."
        )

    if rbf_svc.kernel != "rbf":
        _fail(
            f"rbf_svc must use kernel='rbf'. "
            f"Got {rbf_svc.kernel!r}."
        )

    if not hasattr(rbf_svc, "support_"):
        _fail(
            "rbf_svc does not appear to be fitted."
        )

    if not hasattr(rbf_svc, "support_vectors_"):
        _fail(
            "rbf_svc is missing support_vectors_."
        )

    X_train, X_test, y_train, y_test = _test_data(
        rbf_svc.n_features_in_
    )

    predictions = rbf_svc.predict(X_test)

    if not isinstance(predictions, np.ndarray):
        _fail(
            "rbf_svc.predict() must return a NumPy array."
        )

    if predictions.shape != y_test.shape:
        _fail(
            f"Prediction shape {predictions.shape} does not match "
            f"expected shape {y_test.shape}."
        )

    if not set(np.unique(predictions)).issubset({-1, 1}):
        _fail(
            "rbf_svc predictions must contain only -1 and +1."
        )

    _passed()


# ============================================================
# 5. Sigmoid SVC
# ============================================================

def sigmoid_svc_test(sigmoid_svc):
    """
    Verify that sigmoid_svc is a fitted sigmoid SVC.
    """

    if not isinstance(sigmoid_svc, SVC):
        _fail(
            "sigmoid_svc must be an instance of sklearn.svm.SVC."
        )

    if sigmoid_svc.kernel != "sigmoid":
        _fail(
            f"sigmoid_svc must use kernel='sigmoid'. "
            f"Got {sigmoid_svc.kernel!r}."
        )

    if not hasattr(sigmoid_svc, "support_"):
        _fail(
            "sigmoid_svc does not appear to be fitted."
        )

    if not hasattr(sigmoid_svc, "support_vectors_"):
        _fail(
            "sigmoid_svc is missing support_vectors_."
        )

    X_train, X_test, y_train, y_test = _test_data(
        sigmoid_svc.n_features_in_
    )

    predictions = sigmoid_svc.predict(X_test)

    if not isinstance(predictions, np.ndarray):
        _fail(
            "sigmoid_svc.predict() must return a NumPy array."
        )

    if predictions.shape != y_test.shape:
        _fail(
            f"Prediction shape {predictions.shape} does not match "
            f"expected shape {y_test.shape}."
        )

    if not set(np.unique(predictions)).issubset({-1, 1}):
        _fail(
            "sigmoid_svc predictions must contain only -1 and +1."
        )

    _passed()


# ============================================================
# 6. Kernel comparison
# ============================================================

def kernel_comparison_test(models):
    """
    Verify that all required kernel models exist and are usable.
    """

    if not isinstance(models, dict):
        _fail(
            "models must be a dictionary."
        )

    required_kernels = {
        "linear",
        "polynomial",
        "rbf",
        "sigmoid",
    }

    if set(models.keys()) != required_kernels:
        _fail(
            "models must contain exactly these keys: "
            f"{required_kernels}. "
            f"Got {set(models.keys())}."
        )

    expected_kernels = {
        "linear": "linear",
        "polynomial": "poly",
        "rbf": "rbf",
        "sigmoid": "sigmoid",
    }

    n_features = models["linear"].n_features_in_

    X_train, X_test, y_train, y_test = _test_data(n_features)

    for name, expected_kernel in expected_kernels.items():

        model = models[name]

        if not isinstance(model, SVC):
            _fail(
                f"models['{name}'] must be an SVC instance."
            )

        if model.kernel != expected_kernel:
            _fail(
                f"models['{name}'] must use "
                f"kernel='{expected_kernel}'. "
                f"Got {model.kernel!r}."
            )

        if not hasattr(model, "support_"):
            _fail(
                f"models['{name}'] does not appear to be fitted."
            )

        predictions = model.predict(X_test)

        if predictions.shape != y_test.shape:
            _fail(
                f"models['{name}'] returned predictions with "
                f"shape {predictions.shape}, expected {y_test.shape}."
            )

        if not set(np.unique(predictions)).issubset({-1, 1}):
            _fail(
                f"models['{name}'] predictions must contain "
                "only -1 and +1."
            )

    _passed()