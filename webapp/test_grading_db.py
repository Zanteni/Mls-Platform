from .grading_db import (
    save_grading_result,
    finalize_lab_grade,
)


results = [
    {
        "student": "wajdi-test",
        "lab": "lab3",
        "notebook": "svm_scratch.ipynb",
        "error": None,
        "score": 1.0,
        "checks": [
            {
                "name": "hinge_loss",
                "passed": True,
                "message": "All tests passed!",
            },
            {
                "name": "training",
                "passed": True,
                "message": "All tests passed!",
            },
        ],
    },
    {
        "student": "wajdi-test",
        "lab": "lab3",
        "notebook": "svm_dual.ipynb",
        "error": None,
        "score": 1.0,
        "checks": [
            {
                "name": "kernel_matrix",
                "passed": True,
                "message": "All tests passed!",
            },
            {
                "name": "dual_objective",
                "passed": True,
                "message": "All tests passed!",
            },
            {
                "name": "training",
                "passed": True,
                "message": "All tests passed!",
            },
        ],
    },
]


for result in results:
    notebook_id = save_grading_result(result)
    print(
        f"Saved {result['notebook']} "
        f"-> NotebookResult {notebook_id}"
    )


score = finalize_lab_grade(
    "wajdi-test",
    "lab3",
)

print(
    f"Final automatic grade: {score:.2f}%"
)