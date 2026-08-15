LABS = {
    "lab1": {
        "required_files": [
            {
                "filename": "employee_data.csv",
                "source": "labs/lab1/employee_data.csv",
            }
        ],
        "notebooks": [
            {
                "notebook_filename": "preprocessing_lab.ipynb",
                "hidden_tests_module": "labs/lab1/hidden_tests.py",
                "checks": [
                    ("missing_values", "missing_values_test(df, exp_median, perf_median)"),
                    ("encoding", "encoding_test(df_encoded)"),
                    ("outliers", "outlier_test(df_clean, lower_bound, upper_bound)"),
                    ("split", "split_test(X_train, X_test, y_train, y_test)"),
                    ("scaling", "scaling_test(X_train_scaled, X_test_scaled)"),
                ],
            }
        ],
    },

    "lab2": {
        "required_files": [
            {
                "filename": "employee_data.csv",
                "source": "labs/lab2/employee_data.csv",
            }
        ],

        "notebooks": [
            {
                "notebook_filename": "lin_log_scratch.ipynb",
                "hidden_tests_module": "labs/lab2/hidden_tests_scratch.py",
                "checks": [
                    ("split", "split_test(X_train, X_test, y_salary_train, y_salary_test, y_attrition_train, y_attrition_test)"),
                    ("predict_linear", "predict_linear_test(predict_linear)"),
                    ("compute_cost_linear", "compute_cost_linear_test(compute_cost_linear)"),
                    ("compute_gradient_linear", "compute_gradient_linear_test(compute_gradient_linear)"),
                    ("gradient_descent", "gradient_descent_test(gradient_descent, compute_cost_linear, compute_gradient_linear)"),
                    ("train_linear", "train_linear_test(w_final, b_final, J_history, r2_test)"),
                    ("sigmoid", "sigmoid_test(sigmoid)"),
                    ("predict_logistic", "predict_logistic_test(predict_logistic)"),
                    ("compute_cost_logistic", "compute_cost_logistic_test(compute_cost_logistic)"),
                    ("compute_gradient_logistic", "compute_gradient_logistic_test(compute_gradient_logistic)"),
                    ("train_logistic", "train_logistic_test(w_final_log, b_final_log, J_history_log, acc_test)"),
                ],
            },
            {
                "notebook_filename": "lin_log_sklearn.ipynb",
                "hidden_tests_module": "labs/lab2/hidden_tests_sklearn.py",
                "checks": [
                    ("split", "split_test(X_train, X_test, y_salary_train, y_salary_test, y_attrition_train, y_attrition_test)"),
                    ("linear_model", "linear_model_test(lin_reg, X_test, y_salary_test)"),
                    ("logistic_model", "logistic_model_test(log_reg, X_test, y_attrition_test)"),
                ],
            },
        ],
    },

   "lab3": {
    "required_files": [
        {
            "filename": "employee_data.csv",
            "source": "labs/lab3/employee_data.csv",
        }
    ],

    "notebooks": [
        {
            "notebook_filename": "svm_scratch.ipynb",
            "hidden_tests_module": "labs/lab3/hidden_tests_scratch.py",
            "checks": [
                (
                    "hinge_loss",
                    "hinge_loss_test(hinge_loss)"
                ),
                (
                    "cost",
                    "svm_cost_test(svm_cost)"
                ),
                (
                    "gradient",
                    "svm_gradient_test(svm_gradient)"
                ),
                (
                    "init",
                    "linear_svm_init_test(LinearSVM)"
                ),
                (
                    "fit",
                    "linear_svm_fit_test(LinearSVM)"
                ),
                (
                    "decision_function",
                    "linear_svm_decision_function_test(LinearSVM)"
                ),
                (
                    "predict",
                    "linear_svm_predict_test(LinearSVM)"
                ),
                (
                    "training",
                    "linear_svm_training_test(LinearSVM)"
                ),
            ],
        },

        {
            "notebook_filename": "svm_dual.ipynb",
            "hidden_tests_module": "labs/lab3/hidden_tests_dual.py",
            "checks": [
                (
                    "kernel_matrix",
                    "kernel_matrix_test(kernel_matrix)"
                ),
                (
                    "dual_objective",
                    "dual_objective_test(dual_objective)"
                ),
                (
                    "init",
                    "dual_svm_init_test(DualSVM)"
                ),
                (
                    "fit",
                    "dual_fit_test(DualSVM)"
                ),
                (
                    "alpha_constraints",
                    "alpha_constraints_test(DualSVM)"
                ),
                (
                    "support_vectors",
                    "support_vectors_test(DualSVM)"
                ),
                (
                    "decision_function",
                    "dual_decision_function_test(DualSVM)"
                ),
                (
                    "predict",
                    "dual_predict_test(DualSVM)"
                ),
                (
                    "training",
                    "dual_training_test(DualSVM)"
                ),
                (
                    "primal_dual_consistency",
                    "primal_dual_consistency_test(DualSVM)"
                ),
            ],
        },

        {
            "notebook_filename": "svm_sklearn.ipynb",
            "hidden_tests_module": "labs/lab3/hidden_tests_sklearn.py",
            "checks": [
                (
                    "split",
                    "split_test(X_train, X_test, y_train, y_test)"
                ),
                (
                    "linear_svc",
                    "linear_svc_test(linear_svc)"
                ),
                (
                    "polynomial_svc",
                    "polynomial_svc_test(poly_svc)"
                ),
                (
                    "rbf_svc",
                    "rbf_svc_test(rbf_svc)"
                ),
                (
                    "sigmoid_svc",
                    "sigmoid_svc_test(sigmoid_svc)"
                ),
                (
                    "kernel_comparison",
                    "kernel_comparison_test(models)"
                ),
            ],
        },
    ],
},
}