"""
Hidden tests for Lab 3 — Dual SVM from scratch.

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

def kernel_matrix_test(kernel_matrix):
    """
    Verify that kernel_matrix supports the required kernels.
    """

    X1 = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [-1.0, 2.0],
    ])

    X2 = np.array([
        [2.0, 1.0],
        [0.0, 3.0],
    ])

    # --------------------------------------------------
    # Linear kernel
    # --------------------------------------------------

    result = kernel_matrix(
        X1,
        X2,
        kernel="linear",
    )

    expected = np.array([
        [4.0, 6.0],
        [10.0, 12.0],
        [0.0, 6.0],
    ])

    if not isinstance(result, np.ndarray):
        _fail("kernel_matrix must return a NumPy array.")

    if result.shape != expected.shape:
        _fail(
            f"Linear kernel returned shape {result.shape}, "
            f"expected {expected.shape}."
        )

    if not np.allclose(result, expected, atol=1e-8):
        _fail(
            f"Linear kernel failed.\n"
            f"Expected:\n{expected}\n"
            f"Got:\n{result}"
        )

    # --------------------------------------------------
    # Symmetry check
    # --------------------------------------------------

    K = kernel_matrix(
        X1,
        X1,
        kernel="linear",
    )

    if not np.allclose(K, K.T, atol=1e-8):
        _fail(
            "Kernel matrix K(X, X) must be symmetric."
        )

    # --------------------------------------------------
    # Polynomial kernel
    # --------------------------------------------------

    K_poly = kernel_matrix(
        X1,
        X2,
        kernel="poly",degree=2,gamma=0.1,coef0 =1.0
    )

    if K_poly.shape != (len(X1), len(X2)):
        _fail(
            "Polynomial kernel returned incorrect shape."
        )

    if not np.all(np.isfinite(K_poly)):
        _fail(
            "Polynomial kernel contains NaN or infinity."
        )

    # --------------------------------------------------
    # RBF kernel
    # --------------------------------------------------

    K_rbf = kernel_matrix(
        X1,
        X2,
        kernel="rbf",
        gamma=1.0,
    )

    if K_rbf.shape != (len(X1), len(X2)):
        _fail(
            "RBF kernel returned incorrect shape."
        )

    if not np.all(np.isfinite(K_rbf)):
        _fail(
            "RBF kernel contains NaN or infinity."
        )

    # RBF values must be in (0, 1]
    if np.any(K_rbf <= 0) or np.any(K_rbf > 1 + 1e-8):
        _fail(
            "RBF kernel values must be in the interval (0, 1]."
        )

    # --------------------------------------------------
    # Sigmoid kernel
    # --------------------------------------------------

    K_sigmoid = kernel_matrix(
        X1,
        X2,
        kernel="sigmoid",
        gamma=1.0,
        coef = 0.0
    )

    if K_sigmoid.shape != (len(X1), len(X2)):
        _fail(
            "Sigmoid kernel returned incorrect shape."
        )

    if not np.all(np.isfinite(K_sigmoid)):
        _fail(
            "Sigmoid kernel contains NaN or infinity."
        )

    # --------------------------------------------------
    # Unknown kernel
    # --------------------------------------------------

    try:
        kernel_matrix(
            X1,
            X2,
            kernel="unknown",
        )
    except ValueError:
        pass
    else:
        _fail(
            "kernel_matrix should raise ValueError "
            "for an unsupported kernel."
        )

    _passed()

def dual_objective_test(dual_objective):
    """
    Verify the SVM dual objective on deterministic examples.
    """

    # --------------------------------------------------------
    # Case 1
    # alpha = [1, 0]
    # y = [1, -1]
    # K = I
    #
    # J = -1 + 0.5 * 1 = -0.5
    # --------------------------------------------------------

    alpha = np.array([1.0, 0.0])
    y = np.array([1, -1])

    K = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
    ])

    result = dual_objective(alpha, y, K)

    expected = -0.5

    if not np.isclose(result, expected, atol=1e-8):
        _fail(
            f"dual_objective case 1 failed: "
            f"expected {expected}, got {result}"
        )

    # --------------------------------------------------------
    # Case 2
    #
    # alpha = [1, 1]
    # y = [1, -1]
    # K = I
    #
    # Q = diag(1, 1)
    #
    # J = -(1 + 1) + 0.5*(1 + 1)
    #   = -1
    # --------------------------------------------------------

    alpha = np.array([1.0, 1.0])
    y = np.array([1, -1])

    K = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
    ])

    result = dual_objective(alpha, y, K)

    expected = -1.0

    if not np.isclose(result, expected, atol=1e-8):
        _fail(
            f"dual_objective case 2 failed: "
            f"expected {expected}, got {result}"
        )

    # --------------------------------------------------------
    # Case 3
    #
    # Check interaction between samples.
    # --------------------------------------------------------

    alpha = np.array([0.5, 1.0])
    y = np.array([1, -1])

    K = np.array([
        [2.0, 1.0],
        [1.0, 3.0],
    ])

    # Q = y_i y_j K_ij
    #
    # Q =
    # [[ 2, -1],
    #  [-1,  3]]
    #
    # alpha^T Q alpha = 3
    #
    # J = -1.5 + 0.5*3
    #   = 0
    expected = -0.25

    result = dual_objective(alpha, y, K)

    if not np.isclose(result, expected, atol=1e-8):
        _fail(
            f"dual_objective case 3 failed: "
            f"expected {expected}, got {result}"
        )

    _passed()

# ============================================================
# 3. Fit / training
# ============================================================

def dual_fit_test(DualSVM):
    """
    Verify that fit() trains the model and creates the
    expected learned attributes.
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

    model = DualSVM(
        C=1.0,
        kernel="linear",
    )

    returned = model.fit(X_train, y_train)

    # fit() should return self
    if returned is not model:
        _fail("fit() should return self.")

    # alpha_
    if model.alpha_ is None:
        _fail("fit() must create alpha_.")

    if not isinstance(model.alpha_, np.ndarray):
        _fail("alpha_ must be a NumPy array.")

    if model.alpha_.shape != (len(X_train),):
        _fail(
            f"alpha_ has wrong shape: "
            f"expected {(len(X_train),)}, "
            f"got {model.alpha_.shape}"
        )

    if not np.all(np.isfinite(model.alpha_)):
        _fail("alpha_ contains NaN or infinity.")

    # support indices
    if model.support_indices_ is None:
        _fail("fit() must create support_indices_.")

    if not isinstance(model.support_indices_, np.ndarray):
        _fail("support_indices_ must be a NumPy array.")

    # support vectors
    if model.support_vectors_ is None:
        _fail("fit() must create support_vectors_.")

    if not isinstance(model.support_vectors_, np.ndarray):
        _fail("support_vectors_ must be a NumPy array.")

    if model.support_vectors_.ndim != 2:
        _fail("support_vectors_ must be 2-dimensional.")

    # bias
    if model.b_ is None:
        _fail("fit() must create b_.")

    if not np.isscalar(model.b_):
        _fail("b_ must be a scalar.")

    if not np.isfinite(model.b_):
        _fail("b_ contains NaN or infinity.")

    # linear kernel should recover w
    if model.kernel == "linear":

        if model.w_ is None:
            _fail(
                "w_ must be created when using the linear kernel."
            )

        if not isinstance(model.w_, np.ndarray):
            _fail("w_ must be a NumPy array.")

        if model.w_.shape != (X_train.shape[1],):
            _fail(
                f"w_ has wrong shape: "
                f"expected {(X_train.shape[1],)}, "
                f"got {model.w_.shape}"
            )

        if not np.all(np.isfinite(model.w_)):
            _fail("w_ contains NaN or infinity.")
    if model.X_ is None:
        _fail("fit() must store training data in X_.")

    if model.y_ is None:
        _fail("fit() must store training labels in y_.")

    if not np.array_equal(model.X_, X_train):
        _fail("X_ does not match the training data.")

    if not np.array_equal(model.y_, y_train):
        _fail("y_ does not match the training labels.")

    _passed()

# ============================================================
# 3. Constructor
# ============================================================

def dual_svm_init_test(DualSVM):
    """
    Verify that DualSVM initializes with the expected interface.
    """

    model = DualSVM(
        C=2.5,
        kernel="rbf",
        gamma=0.5,
    )

    if model.C != 2.5:
        _fail(f"C was not stored correctly: {model.C}")

    if model.kernel != "rbf":
        _fail(
            f"kernel was not stored correctly: {model.kernel}"
        )

    # Kernel parameters
    if not isinstance(model.kernel_params, dict):
        _fail("kernel_params must be a dictionary.")

    if model.kernel_params.get("gamma") != 0.5:
        _fail(
            "kernel_params did not store gamma correctly."
        )

    # Learned parameters should initially be None
    if model.alpha_ is not None:
        _fail("alpha_ should initially be None.")

    if model.support_vectors_ is not None:
        _fail("support_vectors_ should initially be None.")

    if model.support_indices_ is not None:
        _fail("support_indices_ should initially be None.")

    if model.w_ is not None:
        _fail("w_ should initially be None.")

    if model.b_ is not None:
        _fail("b_ should initially be None.")

    # Training data should initially be None
    if model.X_ is not None:
        _fail("X_ should initially be None.")

    if model.y_ is not None:
        _fail("y_ should initially be None.")

    # Required methods
    if not callable(getattr(model, "fit", None)):
        _fail("DualSVM must implement fit().")

    if not callable(getattr(model, "decision_function", None)):
        _fail(
            "DualSVM must implement decision_function()."
        )

    if not callable(getattr(model, "predict", None)):
        _fail("DualSVM must implement predict().")

    _passed()

# ============================================================
# 4. Alpha constraints
# ============================================================

# ============================================================
# 4. Alpha constraints
# ============================================================

def alpha_constraints_test(DualSVM):
    """
    Verify that the trained dual SVM satisfies:

        0 <= alpha_i <= C

    and

        sum(alpha_i y_i) = 0
    """

    # --------------------------------------------------------
    # Test data
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Train model
    # --------------------------------------------------------

    model = DualSVM(
        C=1.0,
        kernel="linear",
    )

    model.fit(X_train, y_train)

    alpha = model.alpha_
    C = model.C

    # --------------------------------------------------------
    # Basic checks
    # --------------------------------------------------------

    if not isinstance(alpha, np.ndarray):
        _fail("alpha_ must be a NumPy array.")

    if alpha.shape != (len(X_train),):
        _fail(
            f"alpha_ has wrong shape: "
            f"expected {(len(X_train),)}, "
            f"got {alpha.shape}"
        )

    if not np.all(np.isfinite(alpha)):
        _fail("alpha_ contains NaN or infinity.")

    # --------------------------------------------------------
    # Box constraints
    # --------------------------------------------------------

    if np.any(alpha < -1e-6):
        _fail(
            f"alpha_i must satisfy alpha_i >= 0. "
            f"Got {alpha}"
        )

    if np.any(alpha > C + 1e-6):
        _fail(
            f"alpha_i must satisfy alpha_i <= C. "
            f"C={C}, alpha={alpha}"
        )

    # --------------------------------------------------------
    # Equality constraint
    # --------------------------------------------------------

    equality = np.sum(alpha * y_train)

    if not np.isclose(equality, 0.0, atol=1e-5):
        _fail(
            "Dual equality constraint violated: "
            f"sum(alpha_i * y_i) = {equality}"
        )

    _passed()


# ============================================================
# 5. Support vectors
# ============================================================

def support_vectors_test(DualSVM):
    """
    Verify that fit() correctly identifies support vectors
    from the non-zero alpha values.
    """

    # --------------------------------------------------------
    # Test data
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    model = DualSVM(
        C=1.0,
        kernel="linear",
    )

    model.fit(X_train, y_train)

    # --------------------------------------------------------
    # Check attributes
    # --------------------------------------------------------

    if model.alpha_ is None:
        _fail("alpha_ must be defined after fit().")

    if model.support_indices_ is None:
        _fail(
            "support_indices_ must be defined after fit()."
        )

    if model.support_vectors_ is None:
        _fail(
            "support_vectors_ must be defined after fit()."
        )

    # --------------------------------------------------------
    # Expected support vectors
    # --------------------------------------------------------

    expected_indices = np.where(
        model.alpha_ > 1e-6
    )[0]

    # --------------------------------------------------------
    # Check indices
    # --------------------------------------------------------

    if not np.array_equal(
        model.support_indices_,
        expected_indices,
    ):
        _fail(
            "support_indices_ does not match "
            "the indices where alpha_i > 1e-6."
        )

    # --------------------------------------------------------
    # Check vectors
    # --------------------------------------------------------

    expected_vectors = X_train[expected_indices]

    if not np.array_equal(
        model.support_vectors_,
        expected_vectors,
    ):
        _fail(
            "support_vectors_ does not correspond "
            "to the selected support-vector indices."
        )

    # --------------------------------------------------------
    # At least one support vector
    # --------------------------------------------------------

    if len(model.support_indices_) == 0:
        _fail(
            "A trained SVM should have at least one "
            "support vector."
        )

    _passed()

def dual_decision_function_test(DualSVM):
    """
    Verify that decision_function() works correctly.
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
        [1.0, 1.0],
        [2.0, 2.0],
    ])

    model = DualSVM(
        C=1.0,
        kernel="linear",
    )

    model.fit(X_train, y_train)

    scores = model.decision_function(X_test)

    if not isinstance(scores, np.ndarray):
        _fail(
            "decision_function() must return a NumPy array."
        )

    if scores.shape != (len(X_test),):
        _fail(
            f"decision_function() returned shape {scores.shape}, "
            f"expected {(len(X_test),)}."
        )

    if not np.all(np.isfinite(scores)):
        _fail(
            "decision_function() returned NaN or infinity."
        )

    _passed()


def dual_predict_test(DualSVM):
    """
    Verify that predict() returns valid binary SVM labels.
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
        [1.0, 1.0],
        [2.0, 2.0],
    ])

    model = DualSVM(
        C=1.0,
        kernel="linear",
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    if not isinstance(predictions, np.ndarray):
        _fail(
            "predict() must return a NumPy array."
        )

    if predictions.shape != (len(X_test),):
        _fail(
            f"predict() returned shape {predictions.shape}, "
            f"expected {(len(X_test),)}."
        )

    if not np.all(np.isin(predictions, [-1, 1])):
        _fail(
            "predict() must return only -1 and +1."
        )

    # Predict must agree with decision_function sign
    scores = model.decision_function(X_test)

    expected_predictions = np.where(
        scores >= 0,
        1,
        -1,
    )

    if not np.array_equal(
        predictions,
        expected_predictions,
    ):
        _fail(
            "predict() does not agree with the sign "
            "of decision_function()."
        )

    _passed()
def dual_training_test(DualSVM):
    """
    Verify that DualSVM can train and achieve reasonable
    classification accuracy on a deterministic dataset.
    """

    # --------------------------------------------------
    # Deterministic training data
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Deterministic test data
    # --------------------------------------------------

    X_test = np.array([
        [-2.0, -1.0],
        [-1.0, -2.0],
        [1.0, 2.0],
        [2.0, 1.0],
    ])

    y_test = np.array([
        -1,
        -1,
        1,
        1,
    ])

    # --------------------------------------------------
    # Create and train model
    # --------------------------------------------------

    model = DualSVM(
        C=1.0,
        kernel="linear",
    )

    returned = model.fit(X_train, y_train)

    # fit() should return self
    if returned is not model:
        _fail("fit() should return self.")

    # --------------------------------------------------
    # Check predictions
    # --------------------------------------------------

    predictions = model.predict(X_test)

    if not isinstance(predictions, np.ndarray):
        _fail(
            "predict() must return a NumPy array."
        )

    if predictions.shape != y_test.shape:
        _fail(
            f"Prediction shape {predictions.shape} "
            f"does not match y_test shape "
            f"{y_test.shape}."
        )

    if not np.all(
        np.isin(predictions, [-1, 1])
    ):
        _fail(
            "Predictions must contain only -1 and +1."
        )

    # --------------------------------------------------
    # Accuracy
    # --------------------------------------------------

    accuracy = np.mean(
        predictions == y_test
    )

    if accuracy < 0.75:
        _fail(
            f"DualSVM training accuracy too low: "
            f"{accuracy:.3f}. Expected at least 0.75."
        )

    _passed()

def primal_dual_consistency_test(DualSVM):
    """
    Verify consistency between the dual solution and the
    primal weight vector for a linear SVM.

    For the linear kernel:

        w = sum_i alpha_i y_i x_i
    """

    # --------------------------------------------------
    # Deterministic dataset
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Train dual SVM
    # --------------------------------------------------

    model = DualSVM(
        C=1.0,
        kernel="linear",
    )

    model.fit(X_train, y_train)

    # --------------------------------------------------
    # Check that w_ exists
    # --------------------------------------------------

    if model.w_ is None:
        _fail(
            "Linear DualSVM must compute w_."
        )

    if not isinstance(model.w_, np.ndarray):
        _fail(
            "w_ must be a NumPy array."
        )

    if model.w_.shape != (X_train.shape[1],):
        _fail(
            f"w_ has incorrect shape: "
            f"expected {(X_train.shape[1],)}, "
            f"got {model.w_.shape}."
        )

    # --------------------------------------------------
    # Compute w directly from the dual variables
    # --------------------------------------------------

    expected_w = np.sum(
        (
            model.alpha_ * y_train
        )[:, None] * X_train,
        axis=0,
    )

    # --------------------------------------------------
    # Compare primal and dual representations
    # --------------------------------------------------

    if not np.allclose(
        model.w_,
        expected_w,
        atol=1e-5,
    ):
        _fail(
            "Primal-dual consistency check failed.\n"
            f"Expected w from dual variables:\n"
            f"{expected_w}\n"
            f"Model w_:\n"
            f"{model.w_}"
        )

    # --------------------------------------------------
    # Check that the values are finite
    # --------------------------------------------------

    if not np.all(np.isfinite(model.w_)):
        _fail(
            "w_ contains NaN or infinity."
        )

    _passed()