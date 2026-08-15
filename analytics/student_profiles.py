import pandas as pd


def analyze_students(skill_df):
    """
    Analyze performance for each student.

    Returns one row per student and lab.
    """

    results = []

    grouped = skill_df.groupby(["student", "lab"])

    for (student, lab), group in grouped:

        total_skills = len(group)
        passed_skills = group["passed"].sum()

        score = passed_skills / total_skills if total_skills else 0

        failed_skills = group.loc[
            ~group["passed"], "skill"
        ].tolist()

        results.append(
            {
                "student": student,
                "lab": lab,
                "score": round(score, 4),
                "skills_passed": int(passed_skills),
                "skills_total": total_skills,
                "weak_skills": failed_skills,
            }
        )

    return pd.DataFrame(results)