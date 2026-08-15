from pathlib import Path
import csv
import json

OUTPUT_DIR = Path("dummy_results")
OUTPUT_DIR.mkdir(exist_ok=True)

students = {
    "ahmed": {
        "lab1": [0.60, [1, 0, 1, 1, 0]],
        "lab2": [0.75, [1, 1, 1, 1, 0]],
        "lab3": [0.90, [1, 1, 1, 1, 1]],
    },

    "ali": {
        "lab1": [0.40, [1, 0, 0, 1, 0]],
        "lab2": [0.65, [1, 1, 0, 1, 0]],
        "lab3": [0.50, [1, 0, 0, 1, 0]],
    },

    "sara": {
        "lab1": [0.80, [1, 1, 0, 1, 1]],
        "lab2": [0.80, [1, 1, 0, 1, 1]],
        "lab3": [0.85, [1, 1, 0, 1, 1]],
    },

    "wajdi": {
        "lab1": [1.00, [1, 1, 1, 1, 1]],
        "lab2": [0.95, [1, 1, 1, 1, 1]],
        "lab3": [1.00, [1, 1, 1, 1, 1]],
    },

    # Improving
    "mariem": {
        "lab1": [0.50, [1, 0, 0, 1, 1]],
        "lab2": [0.60, [1, 1, 0, 1, 0]],
        "lab3": [0.70, [1, 1, 1, 1, 0]],
    },

    # Declining
    "yassine": {
        "lab1": [0.70, [1, 1, 0, 1, 1]],
        "lab2": [0.55, [1, 0, 0, 1, 1]],
        "lab3": [0.45, [1, 0, 0, 1, 0]],
    },

    # Strong improvement
    "ines": {
        "lab1": [0.30, [1, 0, 0, 1, 0]],
        "lab2": [0.50, [1, 1, 0, 1, 0]],
        "lab3": [0.75, [1, 1, 1, 1, 0]],
    },

    # Gradual decline
    "mohamed": {
        "lab1": [0.90, [1, 1, 1, 1, 1]],
        "lab2": [0.85, [1, 1, 1, 1, 0]],
        "lab3": [0.80, [1, 1, 0, 1, 1]],
    },

    # Mixed progression
    "nour": {
        "lab1": [0.55, [1, 0, 1, 1, 0]],
        "lab2": [0.70, [1, 1, 1, 1, 0]],
        "lab3": [0.65, [1, 0, 1, 1, 1]],
    },

    # Consistently strong improvement
    "amine": {
        "lab1": [0.85, [1, 1, 1, 1, 0]],
        "lab2": [0.90, [1, 1, 1, 1, 1]],
        "lab3": [0.95, [1, 1, 1, 1, 1]],
    },
}
skills = [
    "missing_values",
    "encoding",
    "outliers",
    "scaling",
    "split",
]

for lab_number in range(1, 4):

    lab = f"lab{lab_number}"
    output_file = OUTPUT_DIR / f"{lab}_dummy.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        writer.writerow([
            "student",
            "lab",
            "notebook",
            "score",
            "checks_passed",
            "checks_total",
            "error",
            "details",
        ])

        for student, labs in students.items():

            score, passed_values = labs[lab]

            checks = [
                {
                    "name": skill,
                    "passed": bool(passed),
                }
                for skill, passed in zip(skills, passed_values)
            ]

            passed_count = sum(passed_values)

            writer.writerow([
                student,
                lab,
                "preprocessing_lab.ipynb",
                score,
                passed_count,
                len(skills),
                "",
                json.dumps(checks),
            ])

    print(f"Created {output_file}")