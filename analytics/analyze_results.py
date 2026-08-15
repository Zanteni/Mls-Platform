from pathlib import Path
import argparse
import json
import pandas as pd

from student_profiles import analyze_students
from progression_analysis import analyze_progression, print_progression
from skill_analysis import analyze_skills
from plots import generate_all_plots

GRADES_DIR = Path(__file__).parent.parent
REAL_RESULTS_DIR = GRADES_DIR / "results"
DUMMY_RESULTS_DIR = GRADES_DIR / "dummy_results"

def load_results(results_dir):
    """Load grading results and keep only the latest run per student/lab/notebook."""

    csv_files = sorted(results_dir.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"No grading result CSV files found in {results_dir}"
        )

    frames = []

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        df["source_file"] = csv_file.name
        frames.append(df)

    results = pd.concat(frames, ignore_index=True)

    # Keep only the latest grading result for each submission.
    results = (
        results
        .drop_duplicates(
            subset=["student", "lab", "notebook"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return results

def build_skill_dataframe(results_df):
    """
    Convert the JSON stored in the 'details' column into
    one row per student/lab/skill.
    """

    rows = []

    for _, result in results_df.iterrows():

        details = result["details"]

        if pd.isna(details) or not details:
            continue

        try:
            checks = json.loads(details)
        except json.JSONDecodeError:
            continue

        for check in checks:
            rows.append(
                {
                    "student": result["student"],
                    "lab": result["lab"],
                    "notebook": result["notebook"],
                    "skill": check["name"],
                    "passed": bool(check["passed"]),
                    "source_file": result["source_file"],
                }
            )

    return pd.DataFrame(rows)


def print_overall_summary(results_df):
    """Print high-level class statistics."""

    students = results_df["student"].nunique()
    labs = results_df["lab"].nunique()
    average_score = results_df["score"].mean()

    print("\n" + "=" * 60)
    print("ML LAB ANALYTICS")
    print("=" * 60)

    print(f"\nStudents analyzed : {students}")
    print(f"Labs analyzed     : {labs}")
    print(f"Average score     : {average_score:.1%}")


def print_class_skill_summary(skill_results):
    """Print strongest and weakest skills across the class."""

    print("\n" + "-" * 60)
    print("CLASS WEAKNESSES")
    print("-" * 60)

    weaknesses = skill_results[
        skill_results["failure_rate"] > 0
    ].sort_values("mastery")

    if weaknesses.empty:
        print("No weaknesses detected.")
    else:
        for _, row in weaknesses.iterrows():
            print(
                f"{row['skill']:<18}"
                f"{row['mastery']:.0%} mastery   "
                f"{row['students_failed']}/{row['students_total']} failed"
            )

    print("\n" + "-" * 60)
    print("CLASS STRENGTHS")
    print("-" * 60)

    strengths = skill_results[
        skill_results["failure_rate"] == 0
    ].sort_values("mastery", ascending=False)

    if strengths.empty:
        print("No completely mastered skills yet.")
    else:
        for _, row in strengths.iterrows():
            print(
                f"{row['skill']:<18}"
                f"{row['mastery']:.0%} mastery"
            )


def print_student_summary(student_results, skill_df):
    """Print a readable profile for every student."""

    print("\n" + "-" * 60)
    print("STUDENT PROFILES")
    print("-" * 60)

    for _, row in student_results.iterrows():

        print(f"\n{row['student']}")

        print(f"  Lab:   {row['lab']}")
        print(f"  Score: {row['score']:.0%}")

        student_skills = skill_df[
            (skill_df["student"] == row["student"])
            & (skill_df["lab"] == row["lab"])
        ]

        strong_skills = student_skills.loc[
            student_skills["passed"], "skill"
        ].tolist()

        weak_skills = student_skills.loc[
            ~student_skills["passed"], "skill"
        ].tolist()

        if strong_skills:
            print(
                "  Strong: "
                + ", ".join(strong_skills)
            )
        else:
            print("  Strong: none")

        if weak_skills:
            print(
                "  Weak:   "
                + ", ".join(weak_skills)
            )
        else:
            print("  Weak:   none")
def main():

    parser = argparse.ArgumentParser(
        description="Analyze ML lab grading results."
    )

    parser.add_argument(
        "--source",
        choices=["real", "dummy"],
        default="real",
        help="Which results to analyze: real or dummy.",
    )

    args = parser.parse_args()

    if args.source == "dummy":
        results_dir = DUMMY_RESULTS_DIR
    else:
        results_dir = REAL_RESULTS_DIR

    print(f"Loading grading results from: {results_dir}")

    # ---------------------------------------------------------
    # 1. Load grading results
    # ---------------------------------------------------------

    results_df = load_results(results_dir)

    print(f"Loaded {len(results_df)} grading records.")

    skill_df = build_skill_dataframe(results_df)

    print(f"Extracted {len(skill_df)} skill results.")

    if skill_df.empty:
        print("No skill-level results found.")
        return

    progression_results = analyze_progression(results_df)
    print_progression(progression_results)
    # ---------------------------------------------------------
    # 3. Analyze students
    # ---------------------------------------------------------

    student_results = analyze_students(skill_df)

    # ---------------------------------------------------------
    # 4. Analyze skills across the class
    # ---------------------------------------------------------

    skill_results = analyze_skills(skill_df)

    # ---------------------------------------------------------
    # 5. Print instructor report
    # ---------------------------------------------------------

    print_overall_summary(results_df)

    print_class_skill_summary(skill_results)

    print_student_summary(student_results, skill_df)

    # ---------------------------------------------------------
    # 6. Generate plots
    # ---------------------------------------------------------

    plot_dir = (
        GRADES_DIR
        / "analytics_outputs"
        / args.source
        / "plots"
    )

    plot_paths = generate_all_plots(
    results_df,
    student_results,
    skill_results,
    plot_dir,
    )

    print("\n" + "-" * 60)
    print("PLOTS")
    print("-" * 60)

    for name, path in plot_paths.items():
        print(f"{name:<20} {path}")


if __name__ == "__main__":
    main()