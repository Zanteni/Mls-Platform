"""
Hidden tests for Lab 3 — Linear SVM from scratch.

This file must NEVER be included in student repositories.

The tests verify behavior, not the student's exact implementation.
"""

import numpy as np


# ============================================================
# Helpers
# ============================================================

def _passed():
    print("\033[92mAll tests passed!\033[0m")


def _fail(message):
    raise AssertionError(message)


# ============================================================
# 1. Hinge loss
# ============================================================

def hinge_loss_test(hinge_loss):
    """
    Verify mean hinge loss on deterministic examples.
    """

    # Case 1
    # margins = [1, 1, 3]
    # losses  = [0, 0, 0]
    X = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
        [1.0, -2.0],
    ])

    y = np.array([1, -1, 1])

    w = np.array([1.0, -1.0])
    b = 0.0

    result = hinge_loss(w, b, X, y)

    expected = 0.0

    if not np.isclose(result, expected, atol=1e-8):
        _fail(
            f"hinge_loss case 1 failed: "
            f"expected {expected}, got {result}"
        )

    # Case 2
    #
    # scores = [0, 0, 0]
    # margins = [0, 0, 0]
    # losses = [1, 1, 1]
    # mean = 1
    X = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
        [1.0, 1.0],
    ])

    y = np.array([1, -1, 1])

    w = np.array([0.0, 0.0])
    b = 0.0

    result = hinge_loss(w, b, X, y)

    expected = 1.0

    if not np.isclose(result, expected, atol=1e-8):
        _fail(
            f"hinge_loss case 2 failed: "
            f"expected {expected}, got {result}"
        )

    # Case 3
    #
    # scores = [2, -0.5]
    # margins = [2, -0.5]
    # losses = [0, 1.5]
    # mean = 0.75
    X = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
    ])

    y = np.array([1, 1])

    w = np.array([2.0, -0.5])
    b = 0.0

    result = hinge_loss(w, b, X, y)

    expected = 0.75

    if not np.isclose(result, expected, atol=1e-8):
        _fail(
            f"hinge_loss case 3 failed: "
            f"expected {expected}, got {result}"
        )

    _passed()

# ============================================================
# 2. SVM cost
# ============================================================

def svm_cost_test(svm_cost):
    """
    Verify:

        J = 0.5 * ||w||² + C * mean_hinge_loss
    """

    X = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
    ])

    y = np.array([1, -1])

    w = np.array([1.0, 2.0])
    b = 0.0
    C = 0.5

    #
    # scores:
    # [1, 2]
    #
    # margins:
    # [1*1, -1*2] = [1, -2]
    #
    # hinge:
    # [0, 3]
    #
    # mean hinge = 1.5
    #
    # regularization = 0.5 * (1² + 2²) = 2.5
    #
    # cost = 2.5 + 0.5 * 1.5
    #      = 3.25
    #

    expected = 3.25

    result = svm_cost(
        w,
        b,
        X,
        y,
        C,
    )

    if not np.isclose(result, expected, atol=1e-8):
        _fail(
            f"svm_cost failed: "
            f"expected {expected}, got {result}"
        )

    # Additional case where hinge loss is zero.
    X = np.array([
        [2.0, 0.0],
        [0.0, -2.0],
    ])

    y = np.array([1, 1])

    w = np.array([1.0, -1.0])
    b = 0.0
    C = 10.0

    #
    # scores = [2, 2]
    # margins = [2, 2]
    # hinge = 0
    #
    # regularization = 0.5 * 2 = 1
    #

    expected = 1.0

    result = svm_cost(
        w,
        b,
        X,
        y,
        C,
    )

    if not np.isclose(result, expected, atol=1e-8):
        _fail(
            f"svm_cost zero-hinge case failed: "
            f"expected {expected}, got {result}"
        )

    _passed()
#======================================================================
#svm subgradeint test
#=======================================================

def svm_gradient_test(svm_gradient):
    """
    Verify the subgradient of the regularized soft-margin SVM objective.
    """

    # Case 1
    #
    # w = [1, -1], b = 0
    #
    # margins = [1, 1, 3]
    # No hinge losses are active.
    #
    # Therefore:
    # dw = w
    # db = 0
    X = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
        [1.0, -2.0],
    ])

    y = np.array([1, -1, 1])

    w = np.array([1.0, -1.0])
    b = 0.0
    C = 2.0

    dw, db = svm_gradient(w, b, X, y, C)

    expected_dw = np.array([1.0, -1.0])
    expected_db = 0.0

    if not np.allclose(dw, expected_dw, atol=1e-8):
        _fail(
            f"svm_gradient case 1 dw failed: "
            f"expected {expected_dw}, got {dw}"
        )

    if not np.isclose(db, expected_db, atol=1e-8):
        _fail(
            f"svm_gradient case 1 db failed: "
            f"expected {expected_db}, got {db}"
        )

    # Case 2
    #
    # w = [0, 0], b = 0
    # All margins = 0, so every sample is active.
    #
    # hinge contribution:
    # dw = -(C/m) * sum(y_i X_i)
    # db = -(C/m) * sum(y_i)
    X = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
        [1.0, 1.0],
    ])

    y = np.array([1, -1, 1])

    w = np.array([0.0, 0.0])
    b = 0.0
    C = 2.0

    dw, db = svm_gradient(w, b, X, y, C)

    # sum(y_i X_i)
    # = [1, 0] + [0, -1] + [1, 1]
    # = [2, 0]
    #
    # dw = -(2/3) * [2, 0]
    expected_dw = np.array([-4.0 / 3.0, 0.0])

    # sum(y) = 1 - 1 + 1 = 1
    expected_db = -2.0 / 3.0

    if not np.allclose(dw, expected_dw, atol=1e-8):
        _fail(
            f"svm_gradient case 2 dw failed: "
            f"expected {expected_dw}, got {dw}"
        )

    if not np.isclose(db, expected_db, atol=1e-8):
        _fail(
            f"svm_gradient case 2 db failed: "
            f"expected {expected_db}, got {db}"
        )

    _passed()

# ============================================================
# 3. Constructor
# ============================================================

def linear_svm_init_test(LinearSVM):
    """
    Verify that the estimator exposes the expected interface.
    """

    model = LinearSVM(
        C=2.5,
        learning_rate=0.01,
        n_iters=123,
    )

    if model.C != 2.5:
        _fail(
            f"C was not stored correctly: {model.C}"
        )

    if model.learning_rate != 0.01:
        _fail(
            f"learning_rate was not stored correctly: "
            f"{model.learning_rate}"
        )

    if model.n_iters != 123:
        _fail(
            f"n_iters was not stored correctly: "
            f"{model.n_iters}"
        )

    if not hasattr(model, "w_"):
        _fail("LinearSVM must define w_.")

    if not hasattr(model, "b_"):
        _fail("LinearSVM must define b_.")

    if not hasattr(model, "loss_history_"):
        _fail("LinearSVM must define loss_history_.")

    if model.w_ is not None:
        _fail("w_ should initially be None.")

    if model.b_ is not None:
        _fail("b_ should initially be None.")

    if model.loss_history_ != []:
        _fail("loss_history_ should initially be empty.")

    if not callable(getattr(model, "fit", None)):
        _fail("LinearSVM must implement fit().")

    if not callable(getattr(model, "predict", None)):
        _fail("LinearSVM must implement predict().")

    if not callable(getattr(model, "decision_function", None)):
        _fail(
            "LinearSVM must implement decision_function()."
        )

    _passed()


# ============================================================
# 4. Fit
# ============================================================

def linear_svm_fit_test(LinearSVM):
    """
    Verify that fit() trains the model and returns self.
    """

    X = np.array([
        [-2.0, -2.0],
        [-1.0, -1.0],
        [-2.0, -1.0],
        [1.0, 1.0],
        [2.0, 1.0],
        [1.0, 2.0],
    ])

    y = np.array([
        -1,
        -1,
        -1,
        1,
        1,
        1,
    ])

    model = LinearSVM(
        C=1.0,
        learning_rate=0.01,
        n_iters=1000,
    )

    returned = model.fit(X, y)

    if returned is not model:
        _fail(
            "fit() should return self."
        )

    if model.w_ is None:
        _fail("fit() did not create w_.")

    if model.b_ is None:
        _fail("fit() did not create b_.")

    if not isinstance(model.w_, np.ndarray):
        _fail("w_ should be a NumPy array.")

    if model.w_.shape != (X.shape[1],):
        _fail(
            f"w_ has wrong shape: "
            f"expected {(X.shape[1],)}, "
            f"got {model.w_.shape}"
        )

    if not np.isscalar(model.b_):
        _fail("b_ should be a scalar.")

    if not hasattr(model, "loss_history_"):
        _fail("loss_history_ is missing after fit().")

    if len(model.loss_history_) == 0:
        _fail("loss_history_ should not be empty after fit().")

    if not np.all(np.isfinite(model.w_)):
        _fail("w_ contains NaN or infinite values.")

    if not np.isfinite(model.b_):
        _fail("b_ contains NaN or infinite values.")

    _passed()


# ============================================================
# 5. Decision function
# ============================================================

def linear_svm_decision_function_test(LinearSVM):
    """
    Verify decision_function() returns X @ w_ + b_.
    """

    X_train = np.array([
        [-2.0, -2.0],
        [-1.0, -1.0],
        [-2.0, -1.0],
        [1.0, 1.0],
        [2.0, 1.0],
        [1.0, 2.0],
    ])

    y_train = np.array([
        -1,
        -1,
        -1,
        1,
        1,
        1,
    ])

    X_test = np.array([
        [-2.0, -1.0],
        [-1.0, 2.0],
        [0.0, 0.0],
        [1.0, 2.0],
        [2.0, 1.0],
    ])

    model = LinearSVM(
        C=1.0,
        learning_rate=0.01,
        n_iters=1000,
    )

    model.fit(X_train, y_train)

    scores = model.decision_function(X_test)

    expected = X_test @ model.w_ + model.b_

    if not isinstance(scores, np.ndarray):
        _fail(
            "decision_function() should return a NumPy array."
        )

    if scores.shape != (len(X_test),):
        _fail(
            f"decision_function() returned shape {scores.shape}, "
            f"expected {(len(X_test),)}"
        )

    if not np.all(np.isfinite(scores)):
        _fail(
            "decision_function() returned NaN or infinite values."
        )

    if not np.allclose(scores, expected, atol=1e-7):
        _fail(
            "decision_function() does not match X @ w_ + b_."
        )

    _passed()


# ============================================================
# 6. Predict
# ============================================================

def linear_svm_predict_test(LinearSVM):
    """
    Verify that predictions are based on the sign
    of the decision function and belong to {-1, +1}.
    """

    X_train = np.array([
        [-2.0, -2.0],
        [-1.0, -1.0],
        [-2.0, -1.0],
        [1.0, 1.0],
        [2.0, 1.0],
        [1.0, 2.0],
    ])

    y_train = np.array([
        -1,
        -1,
        -1,
        1,
        1,
        1,
    ])

    X_test = np.array([
        [-2.0, -1.0],
        [-1.0, 2.0],
        [0.0, 0.0],
        [1.0, 2.0],
        [2.0, 1.0],
    ])

    model = LinearSVM(
        C=1.0,
        learning_rate=0.01,
        n_iters=1000,
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    if not isinstance(predictions, np.ndarray):
        _fail(
            "predict() should return a NumPy array."
        )

    if predictions.shape != (len(X_test),):
        _fail(
            f"predict() returned shape {predictions.shape}, "
            f"expected {(len(X_test),)}"
        )

    unique_values = set(np.unique(predictions))

    if not unique_values.issubset({-1, 1}):
        _fail(
            "Predictions must contain only -1 and +1. "
            f"Got: {unique_values}"
        )

    scores = model.decision_function(X_test)

    expected = np.where(scores >= 0, 1, -1)

    if not np.array_equal(predictions, expected):
        _fail(
            "predict() must correspond to the sign "
            "of decision_function()."
        )

    _passed()

# ============================================================
# 7. Complete training behavior
# ============================================================

def linear_svm_training_test(LinearSVM):
    """
    Verify that LinearSVM can train a useful linear classifier.

    Everything needed for the test is created internally.
    """

    # --------------------------------------------------------
    # Deterministic linearly separable dataset
    # --------------------------------------------------------

    X_train = np.array([
        [-2.0, -2.0],
        [-1.0, -1.0],
        [-2.0, -1.0],
        [-1.0, -2.0],
        [-3.0, -1.0],
        [-1.0, -3.0],

        [1.0, 1.0],
        [2.0, 1.0],
        [1.0, 2.0],
        [2.0, 2.0],
        [3.0, 1.0],
        [1.0, 3.0],
    ])

    y_train = np.array([
        -1, -1, -1, -1, -1, -1,
         1,  1,  1,  1,  1,  1,
    ])

    # --------------------------------------------------------
    # Separate deterministic test set
    # --------------------------------------------------------

    X_test = np.array([
        [-2.0, -1.0],
        [-1.0, -2.0],
        [-3.0, -2.0],
        [1.0, 2.0],
        [2.0, 1.0],
        [3.0, 2.0],
        [2.0, 3.0],
        [0.8, 1.2],
        [-0.8, -1.2],
        [-1.5, -0.5],
    ])

    y_test = np.array([
        -1,
        -1,
        -1,
         1,
         1,
         1,
         1,
         1,
        -1,
        -1,
    ])

    # --------------------------------------------------------
    # Create and train model
    # --------------------------------------------------------

    model = LinearSVM(
        C=1.0,
        learning_rate=0.01,
        n_iters=1000,
    )

    returned = model.fit(X_train, y_train)

    # fit() should follow sklearn-style behavior
    if returned is not model:
        _fail("fit() should return self.")

    # --------------------------------------------------------
    # Check learned parameters
    # --------------------------------------------------------

    if model.w_ is None:
        _fail("Training did not create w_.")

    if model.b_ is None:
        _fail("Training did not create b_.")

    if len(model.loss_history_) < 2:
        _fail(
            "loss_history_ must contain multiple values."
        )

    losses = np.asarray(
        model.loss_history_,
        dtype=float,
    )

    if not np.all(np.isfinite(losses)):
        _fail(
            "loss_history_ contains NaN or infinite values."
        )

    # --------------------------------------------------------
    # Check optimization progress
    # --------------------------------------------------------

    if losses[-1] >= losses[0]:
        _fail(
            "Training did not reduce the objective. "
            f"Initial loss={losses[0]:.6f}, "
            f"final loss={losses[-1]:.6f}"
        )

    # --------------------------------------------------------
    # Check predictive performance
    # --------------------------------------------------------

    predictions = model.predict(X_test)

    if not isinstance(predictions, np.ndarray):
        _fail(
            "predict() should return a NumPy array."
        )

    if predictions.shape != y_test.shape:
        _fail(
            f"predict() returned shape {predictions.shape}, "
            f"expected {y_test.shape}"
        )

    accuracy = np.mean(predictions == y_test)

    # 10 test samples -> require at least 9/10
    if accuracy < 0.90:
        _fail(
            f"Test accuracy too low: {accuracy:.3f}. "
            "Expected at least 0.90."
        )

    _passed()