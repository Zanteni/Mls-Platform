"""
generate_summary.py — generate readable student reports from grading results.

Usage:
    python generate_summary.py --lab lab1
    python generate_summary.py --lab lab2

The script:
1. Finds the latest analytical CSV for the requested lab.
2. Ignores *_scores.csv files.
3. Parses the JSON details column.
4. Generates one Markdown report per student.
5. Generates a clean summary CSV for later use in Excel, PDFs,
   dashboards, emails, etc.

It does NOT modify the original grading results.
"""

import argparse
import csv
import json
import os
from datetime import datetime


GRADING_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(GRADING_REPO_ROOT, "results")


def find_latest_analytical_csv(lab_id):
    """
    Find the newest analytical CSV for a lab.

    Example:
        lab2_20260810T215215Z.csv

    Excludes:
        lab2_20260810T215215Z_scores.csv
    """

    if not os.path.exists(RESULTS_DIR):
        raise FileNotFoundError(
            f"Results directory not found: {RESULTS_DIR}"
        )

    prefix = f"{lab_id}_"

    candidates = []

    for filename in os.listdir(RESULTS_DIR):
        if not filename.startswith(prefix):
            continue

        if not filename.endswith(".csv"):
            continue

        if filename.endswith("_scores.csv"):
            continue

        path = os.path.join(RESULTS_DIR, filename)

        if os.path.isfile(path):
            candidates.append(path)

    if not candidates:
        raise FileNotFoundError(
            f"No analytical results found for {lab_id}"
        )

    return max(candidates, key=os.path.getmtime)


def load_results(csv_path):
    """Load analytical grading results."""

    results = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:

            # Parse the JSON containing individual checks.
            try:
                row["details"] = json.loads(row["details"])
            except (json.JSONDecodeError, TypeError):
                row["details"] = []

            # Convert numeric values.
            try:
                row["score"] = float(row["score"])
            except (ValueError, TypeError):
                row["score"] = 0.0

            try:
                row["checks_passed"] = int(row["checks_passed"])
            except (ValueError, TypeError):
                row["checks_passed"] = 0

            try:
                row["checks_total"] = int(row["checks_total"])
            except (ValueError, TypeError):
                row["checks_total"] = 0

            results.append(row)

    return results


def group_by_student(results):
    """Group notebook results by student."""

    students = {}

    for result in results:
        student = result["student"]

        if student not in students:
            students[student] = []

        students[student].append(result)

    return students


def calculate_student_summary(student_results):
    """Calculate overall statistics for one student."""

    checks_passed = sum(
        result["checks_passed"]
        for result in student_results
    )

    checks_total = sum(
        result["checks_total"]
        for result in student_results
    )

    # The notebook scores are check-based, so calculate the overall
    # score from all checks rather than averaging notebook percentages.
    base_score = (
        100 * checks_passed / checks_total
        if checks_total
        else 0.0
    )

    # Bonus is currently stored in the separate scores CSV.
    # Until bonuses are integrated, this remains zero.
    bonus = 0.0

    final_score = base_score + bonus

    execution_errors = sum(
        1
        for result in student_results
        if result.get("error")
    )

    if execution_errors:
        status = "Execution error"
    elif checks_total == 0:
        status = "No checks"
    elif checks_passed == checks_total:
        status = "Complete"
    else:
        status = "Needs attention"

    return {
        "base_score": round(base_score, 2),
        "bonus": round(bonus, 2),
        "final_score": round(final_score, 2),
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "notebooks": len(student_results),
        "execution_errors": execution_errors,
        "status": status,
    }


def check_symbol(passed):
    """Return a simple readable symbol."""

    return "✓" if passed else "✗"


def generate_student_report(student, lab_id, student_results):
    """Generate one Markdown report for a student."""

    summary = calculate_student_summary(student_results)

    lines = []

    lines.append(f"# {lab_id.upper()} — Grading Summary")
    lines.append("")
    lines.append(f"**Student:** {student}")
    lines.append("")

    # ---------------------------------------------------------
    # Final score
    # ---------------------------------------------------------

    lines.append("## Final Score")
    lines.append("")

    lines.append("| Metric | Result |")
    lines.append("|---|---:|")
    lines.append(
        f"| Base score | {summary['base_score']:.2f}% |"
    )
    lines.append(
        f"| Bonus | +{summary['bonus']:.2f} |"
    )
    lines.append(
        f"| **Final score** | **{summary['final_score']:.2f}%** |"
    )
    lines.append(
        f"| Checks | "
        f"{summary['checks_passed']}/{summary['checks_total']} |"
    )
    lines.append(
        f"| Status | **{summary['status']}** |"
    )
    lines.append("")

    # ---------------------------------------------------------
    # Notebook results
    # ---------------------------------------------------------

    lines.append("## Notebook Results")
    lines.append("")

    for index, result in enumerate(student_results, start=1):

        notebook = result["notebook"]

        lines.append(
            f"### {index}. `{notebook}`"
        )
        lines.append("")

        lines.append(
            f"**Score:** {result['score'] * 100:.2f}%"
        )

        lines.append(
            f"  \n**Checks:** "
            f"{result['checks_passed']}/"
            f"{result['checks_total']}"
        )

        lines.append("")

        # Notebook execution error
        if result.get("error"):
            lines.append("#### Execution Error")
            lines.append("")
            lines.append(
                f"> {result['error']}"
            )
            lines.append("")

        # Checks table
        if result["details"]:

            lines.append("| Check | Result |")
            lines.append("|---|---|")

            for check in result["details"]:

                name = check.get("name", "unknown")
                passed = check.get("passed", False)

                symbol = check_symbol(passed)

                status = (
                    f"{symbol} Passed"
                    if passed
                    else f"{symbol} Failed"
                )

                lines.append(
                    f"| `{name}` | {status} |"
                )

            lines.append("")

            # Explicit failed checks
            failed_checks = [
                check.get("name", "unknown")
                for check in result["details"]
                if not check.get("passed", False)
            ]

            if failed_checks:

                lines.append("#### Checks needing attention")
                lines.append("")

                for check_name in failed_checks:
                    lines.append(
                        f"- `{check_name}`"
                    )

                lines.append("")

    # ---------------------------------------------------------
    # Overall
    # ---------------------------------------------------------

    lines.append("## Overall")
    lines.append("")

    lines.append(
        f"**{summary['checks_passed']}/"
        f"{summary['checks_total']} checks passed.**"
    )

    lines.append("")

    lines.append(
        f"Status: **{summary['status']}**"
    )

    lines.append("")

    lines.append(
        "---"
    )

    lines.append(
        "*Generated automatically by the lab grading system.*"
    )

    return "\n".join(lines)


def write_student_reports(lab_id, students):
    """Write one Markdown report per student."""

    reports_dir = os.path.join(
        RESULTS_DIR,
        "summaries",
    )

    os.makedirs(
        reports_dir,
        exist_ok=True,
    )

    paths = []

    for student, student_results in students.items():

        report = generate_student_report(
            student,
            lab_id,
            student_results,
        )

        filename = f"{student}_{lab_id}.md"

        path = os.path.join(
            reports_dir,
            filename,
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(report)

        paths.append(path)

    return paths


def write_summary_csv(lab_id, students):
    """
    Create a clean machine-readable summary CSV.

    This is intentionally separate from the analytical CSV.
    """

    reports_dir = os.path.join(
        RESULTS_DIR,
        "summaries",
    )

    os.makedirs(
        reports_dir,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%dT%H%M%S"
    )

    path = os.path.join(
        reports_dir,
        f"{lab_id}_{timestamp}_summary.csv",
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "student",
            "lab",
            "final_score",
            "notebooks",
            "checks_passed",
            "checks_total",
            "execution_errors",
            "status",
        ])

        for student, student_results in students.items():

            summary = calculate_student_summary(
                student_results
            )

            writer.writerow([
                student,
                lab_id,
                summary["final_score"],
                summary["notebooks"],
                summary["checks_passed"],
                summary["checks_total"],
                summary["execution_errors"],
                summary["status"],
            ])

    return path


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generate readable student reports "
            "from lab grading results."
        )
    )

    parser.add_argument(
        "--lab",
        required=True,
        help="Lab identifier, e.g. lab1 or lab2",
    )

    args = parser.parse_args()

    lab_id = args.lab

    # ---------------------------------------------------------
    # Find latest analytical result
    # ---------------------------------------------------------

    csv_path = find_latest_analytical_csv(
        lab_id
    )

    print(
        f"Using analytical results: {csv_path}"
    )

    # ---------------------------------------------------------
    # Load and group
    # ---------------------------------------------------------

    results = load_results(csv_path)

    if not results:
        print("No grading results found.")
        return

    students = group_by_student(results)

    # ---------------------------------------------------------
    # Generate reports
    # ---------------------------------------------------------

    report_paths = write_student_reports(
        lab_id,
        students,
    )

    # ---------------------------------------------------------
    # Generate summary CSV
    # ---------------------------------------------------------

    summary_path = write_summary_csv(
        lab_id,
        students,
    )

    # ---------------------------------------------------------
    # Print result
    # ---------------------------------------------------------

    print("")
    print(
        f"Generated {len(report_paths)} student reports."
    )

    for path in report_paths:
        print(f"  {path}")

    print("")
    print(
        f"Wrote summary CSV to:"
        f"\n  {summary_path}"
    )


if __name__ == "__main__":
    main()