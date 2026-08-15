import pandas as pd


def analyze_skills(skill_df):
    """
    Analyze mastery of each skill across students.
    """

    results = []

    grouped = skill_df.groupby(["lab", "skill"])

    for (lab, skill), group in grouped:

        total = len(group)
        passed = int(group["passed"].sum())
        failed = total - passed

        mastery = passed / total if total else 0

        results.append(
            {
                "lab": lab,
                "skill": skill,
                "mastery": round(mastery, 4),
                "students_passed": passed,
                "students_failed": failed,
                "students_total": total,
                "failure_rate": round(1 - mastery, 4),
            }
        )

    return (
        pd.DataFrame(results)
        .sort_values(["lab", "mastery", "skill"])
        .reset_index(drop=True)
    )