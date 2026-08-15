"""
grade.py — pull-based grading for the labs.

For each student in roster.csv, and each lab requested:
    1. Fetch the student's submission (local path or git clone).
    2. Execute their notebook end-to-end in a fresh Jupyter kernel.
    3. Inject the real hidden test module into the live kernel.
    4. Run each configured check.
    5. Record pass/fail per check.
    6. Write detailed and final score CSV files.

The hidden tests are copied only into the temporary grading directory.
They are never written into the student's repository.

Usage:
    python grade.py --lab lab1
    python grade.py --lab lab1 --student ahmed_hdhili
    python grade.py --lab lab1 --local-fixture /path/to/submission/dir
"""

import argparse
import asyncio
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import warnings


from pathlib import Path
# ============================================================
# Windows / environment configuration
# ============================================================

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

# Limit loky CPU detection in the grading environment.
# This helps avoid excessive parallel worker management.
os.environ["LOKY_MAX_CPU_COUNT"] = "1"


# ============================================================
# Jupyter / nbformat imports
# ============================================================

from datetime import datetime, timezone

from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

import nbformat
from nbformat.validator import MissingIDFieldWarning


# Suppress the warning emitted when older notebooks do not
# contain explicit cell IDs.
warnings.filterwarnings(
    "ignore",
    category=MissingIDFieldWarning,
)


from Labs_config import LABS


GRADING_REPO_ROOT = os.path.dirname(
    os.path.abspath(__file__)
)


# ============================================================
# Roster
# ============================================================

def load_roster(path="roster.csv"):
    """
    Load students from roster.csv.
    """

    roster = []

    full_path = os.path.join(
        GRADING_REPO_ROOT,
        path,
    )

    if not os.path.exists(full_path):
        return roster

    with open(
        full_path,
        newline="",
        encoding="utf-8",
    ) as f:
        for row in csv.DictReader(f):
            roster.append(row)

    return roster


# ============================================================
# Submission fetching
# ============================================================

def fetch_submission(student, workdir):
    """
    Clone the student's private repository into workdir.

    Requires GH_TOKEN with read access.
    """

    repo_url = student["repo_url"]

    token = os.environ.get("GH_TOKEN")

    if token and repo_url.startswith("https://"):
        repo_url = repo_url.replace(
            "https://",
            f"https://x-access-token:{token}@",
            1,
        )

    try:
        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                repo_url,
                workdir,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        # Git clone progress is usually written to stderr.
        if result.stderr.strip():
            print(
                f"git clone: {result.stderr.strip()}",
                file=sys.stderr,
            )

    except subprocess.CalledProcessError as e:

        error_output = (
            e.stderr.strip()
            if e.stderr
            else e.stdout.strip()
        )

        if not error_output:
            error_output = (
                "Git did not provide an error message."
            )

        raise RuntimeError(
            f"Could not clone repository for "
            f"student '{student['student_id']}'.\n"
            f"Repository: {student['repo_url']}\n"
            f"Git error:\n{error_output}"
        ) from e
def fetch_snapshot(snapshot_path, workdir):
    """
    Copy an immutable submitted snapshot into the grading workdir.

    The snapshot was created at submission time and must never
    be replaced with the student's current GitHub repository.
    """

    if not snapshot_path:
        raise ValueError(
            "No snapshot path was provided for this submission."
        )

    if not os.path.isdir(snapshot_path):
        raise FileNotFoundError(
            f"Submission snapshot does not exist: {snapshot_path}"
        )

    if os.path.exists(workdir):
        shutil.rmtree(workdir)

    shutil.copytree(
        snapshot_path,
        workdir,
    )

    return workdir

# ============================================================
# Hidden-test execution
# ============================================================

def run_check(
    client,
    kernel,
    check_name,
    check_call,
):
    """
    Execute one hidden-test call in the already-running kernel.

    Returns
    -------
    tuple
        (passed, message)
    """

    cell = nbformat.v4.new_code_cell(
        source=check_call
    )

    try:

        client.execute_cell(
            cell,
            0,
        )

        outputs = cell.get(
            "outputs",
            [],
        )

        text = "".join(
            output.get("text", "")
            for output in outputs
            if output.get("output_type") == "stream"
        )

        return True, text.strip()

    except CellExecutionError as e:

        lines = str(e).splitlines()

        return (
            False,
            lines[-1] if lines else str(e),
        )


# ============================================================
# Required files
# ============================================================

def prepare_required_files(
    submission_dir,
    required_files,
):
    """
    Copy required grading files into the temporary submission
    directory only when the student did not provide them.
    """

    for file_cfg in required_files:

        filename = file_cfg["filename"]
        source = file_cfg["source"]

        destination = os.path.join(
            submission_dir,
            filename,
        )

        source_path = os.path.join(
            GRADING_REPO_ROOT,
            source,
        )

        # Student already provided the file.
        if os.path.exists(destination):
            continue

        if not os.path.exists(source_path):
            raise FileNotFoundError(
                f"Required grading file not found: "
                f"{source_path}"
            )

        shutil.copy2(
            source_path,
            destination,
        )


# ============================================================
# Notebook grading
# ============================================================

def grade_notebook(
    submission_dir,
    notebook_filename,
    hidden_tests_module,
    checks,
    required_files=None,
):
    """
    Execute one student's notebook and then run the hidden tests
    against the same live kernel.
    """

    if required_files is None:
        required_files = []

    # --------------------------------------------------------
    # Locate notebook
    # --------------------------------------------------------

    nb_path = os.path.join(
        submission_dir,
        notebook_filename,
    )

    if not os.path.exists(nb_path):
        return {
            "notebook": notebook_filename,
            "error": "notebook not found in submission",
            "checks": [],
            "score": 0.0,
        }

    # --------------------------------------------------------
    # Required files
    # --------------------------------------------------------

    try:

        prepare_required_files(
            submission_dir,
            required_files,
        )

    except Exception as e:

        return {
            "notebook": notebook_filename,
            "error": str(e),
            "checks": [],
            "score": 0.0,
        }

    # --------------------------------------------------------
    # Hidden tests
    # --------------------------------------------------------

    hidden_tests_src = os.path.join(
        GRADING_REPO_ROOT,
        hidden_tests_module,
    )

    if not os.path.exists(hidden_tests_src):
        return {
            "notebook": notebook_filename,
            "error": (
                "hidden test module not found: "
                f"{hidden_tests_src}"
            ),
            "checks": [],
            "score": 0.0,
        }

    hidden_tests_dst = os.path.join(
        submission_dir,
        "_hidden_tests.py",
    )

    shutil.copy2(
        hidden_tests_src,
        hidden_tests_dst,
    )

    # --------------------------------------------------------
    # Read notebook
    # --------------------------------------------------------

    try:

        nb = nbformat.read(
            nb_path,
            as_version=4,
        )

    except Exception as e:

        if os.path.exists(hidden_tests_dst):
            os.remove(hidden_tests_dst)

        return {
            "notebook": notebook_filename,
            "error": (
                f"could not read notebook: {e}"
            ),
            "checks": [],
            "score": 0.0,
        }

    # --------------------------------------------------------
    # Normalize notebook
    # --------------------------------------------------------
    #
    # IMPORTANT:
    #
    # Do NOT write:
    #
    #     nb, _ = nbformat.validator.normalize(nb)
    #
    # because normalize() does not return the notebook in the
    # first position in the version installed here.
    #
    # Normalize in-place instead.
    #

    try:

        nbformat.validator.normalize(nb)

    except Exception as e:

        if os.path.exists(hidden_tests_dst):
            os.remove(hidden_tests_dst)

        return {
            "notebook": notebook_filename,
            "error": (
                f"could not normalize notebook: {e}"
            ),
            "checks": [],
            "score": 0.0,
        }

    # --------------------------------------------------------
    # Notebook client
    # --------------------------------------------------------

    client = NotebookClient(
        nb,
        timeout=120,
        resources={
            "metadata": {
                "path": submission_dir,
            }
        },
    )

    results = {
        "notebook": notebook_filename,
        "error": None,
        "checks": [],
        "score": 0.0,
    }

    try:

        with client.setup_kernel():

            # ------------------------------------------------
            # Execute student notebook
            # ------------------------------------------------

            try:

                for index, cell in enumerate(nb.cells):

                    if cell.cell_type != "code":
                        continue

                    client.execute_cell(
                        cell,
                        index,
                    )

            except CellExecutionError as e:

                lines = str(e).splitlines()

                results["error"] = (
                    "student notebook failed to execute: "
                    + (
                        lines[-1]
                        if lines
                        else str(e)
                    )
                )

                return results

            # ------------------------------------------------
            # Inject hidden tests
            # ------------------------------------------------

            import_cell = nbformat.v4.new_code_cell(
                source="from _hidden_tests import *"
            )

            try:

                client.execute_cell(
                    import_cell,
                    0,
                )

            except CellExecutionError as e:

                lines = str(e).splitlines()

                results["error"] = (
                    "could not load hidden tests: "
                    + (
                        lines[-1]
                        if lines
                        else str(e)
                    )
                )

                return results

            # ------------------------------------------------
            # Run checks
            # ------------------------------------------------

            passed_count = 0

            for check_name, check_call in checks:

                passed, message = run_check(
                    client,
                    None,
                    check_name,
                    check_call,
                )

                results["checks"].append(
                    {
                        "name": check_name,
                        "passed": passed,
                        "message": message,
                    }
                )

                if passed:
                    passed_count += 1

            # ------------------------------------------------
            # Score
            # ------------------------------------------------

            results["score"] = (
                round(
                    passed_count / len(checks),
                    4,
                )
                if checks
                else 0.0
            )

            return results

    except Exception as e:

        results["error"] = (
            f"grading notebook failed: {e}"
        )

        return results

    finally:

        # Always remove hidden tests from the temporary clone.
        if os.path.exists(hidden_tests_dst):

            try:
                os.remove(hidden_tests_dst)
            except OSError:
                pass


# ============================================================
# Student / Lab Grading
# ============================================================

def grade_student_lab(
    student_id,
    submission_dir,
    lab_id,
    notebook_filename=None,
    submission_id=None,
):
    """
    Grade one student's lab.

    IMPORTANT:
    This function does NOT write to the application database.

    It only:
        1. executes the notebooks,
        2. runs hidden checks,
        3. returns grading results.

    Database persistence is handled by the Flask application.
    """

    lab_cfg = LABS[lab_id]

    all_results = []

    required_files = lab_cfg.get(
        "required_files",
        [],
    )

    for nb_cfg in lab_cfg["notebooks"]:

        # ----------------------------------------------------
        # Optional notebook filter
        # ----------------------------------------------------

        if (
            notebook_filename is not None
            and nb_cfg["notebook_filename"]
            != notebook_filename
        ):
            continue

        # ----------------------------------------------------
        # Grade notebook
        # ----------------------------------------------------

        result = grade_notebook(
            submission_dir,
            nb_cfg["notebook_filename"],
            nb_cfg["hidden_tests_module"],
            nb_cfg["checks"],
            required_files,
        )

        # ----------------------------------------------------
        # Attach identifying information
        # ----------------------------------------------------

        result["student"] = student_id
        result["lab"] = lab_id

        if submission_id is not None:

            result["submission_id"] = (
                submission_id
            )

        all_results.append(
            result
        )

    return all_results

# ============================================================
# Score computation
# ============================================================

def compute_lab_score(
    results,
    bonus=0,
):
    """
    Compute the final score for one student/lab.
    """

    total_passed = sum(
        sum(
            1
            for check in result["checks"]
            if check["passed"]
        )
        for result in results
    )

    total_checks = sum(
        len(result["checks"])
        for result in results
    )

    base_score = (
        100 * total_passed / total_checks
        if total_checks
        else 0.0
    )

    final_score = base_score + bonus

    return {
        "base_score": round(
            base_score,
            2,
        ),
        "bonus": bonus,
        "final_score": round(
            final_score,
            2,
        ),
        "checks_passed": total_passed,
        "checks_total": total_checks,
    }


# ============================================================
# Result writing
# ============================================================

def write_results(
    results,
    lab_id,
):
    """
    Write detailed notebook-level results and
    student-level final scores.
    """

    out_dir = os.path.join(
        GRADING_REPO_ROOT,
        "results",
    )

    os.makedirs(
        out_dir,
        exist_ok=True,
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    # --------------------------------------------------------
    # Detailed results
    # --------------------------------------------------------

    detail_path = os.path.join(
        out_dir,
        f"{lab_id}_{timestamp}.csv",
    )

    with open(
        detail_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [
                "student",
                "lab",
                "notebook",
                "score",
                "checks_passed",
                "checks_total",
                "error",
                "details",
            ]
        )

        for result in results:

            checks_passed = sum(
                1
                for check in result["checks"]
                if check["passed"]
            )

            writer.writerow(
                [
                    result["student"],
                    result["lab"],
                    result["notebook"],
                    result["score"],
                    checks_passed,
                    len(result["checks"]),
                    result["error"] or "",
                    json.dumps(
                        result["checks"]
                    ),
                ]
            )

    # --------------------------------------------------------
    # Group by student
    # --------------------------------------------------------

    students = {}

    for result in results:

        student = result["student"]

        if student not in students:
            students[student] = []

        students[student].append(
            result
        )

    # --------------------------------------------------------
    # Final scores
    # --------------------------------------------------------

    score_path = os.path.join(
        out_dir,
        f"{lab_id}_{timestamp}_scores.csv",
    )

    with open(
        score_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [
                "student",
                "lab",
                "base_score",
                "bonus",
                "final_score",
                "checks_passed",
                "checks_total",
            ]
        )

        for student, student_results in students.items():

            # Bonus currently fixed at zero.
            bonus = 0

            score = compute_lab_score(
                student_results,
                bonus=bonus,
            )

            writer.writerow(
                [
                    student,
                    lab_id,
                    score["base_score"],
                    score["bonus"],
                    score["final_score"],
                    score["checks_passed"],
                    score["checks_total"],
                ]
            )

    print(
        f"Wrote detailed results to {detail_path}"
    )

    print(
        f"Wrote final scores to {score_path}"
    )

    return detail_path, score_path

def grade_submission(
    student_id,
    lab_id,
    snapshot_path=None,
    repo_url=None,
    notebook_filename=None,
    submission_id=None,
):
    """
    Grade one student's repository.

    notebook_filename=None
        -> grade the entire lab

    notebook_filename="svm_dual.ipynb"
        -> grade only that notebook
    """

    with tempfile.TemporaryDirectory() as workdir:
        #here
        if snapshot_path:
            fetch_snapshot(
                snapshot_path,
                workdir,
            )

        elif repo_url:
            student = {
                "student_id": student_id,
                "repo_url": repo_url,
            }

            fetch_submission(
                student,
                workdir,
            )

        else:
            raise ValueError(
                "Either snapshot_path or repo_url must be provided."
            )

        return grade_student_lab(
            student_id,
            workdir,
            lab_id,
            notebook_filename=notebook_filename,
            submission_id=submission_id,
        )
# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--lab",
        required=True,
        choices=list(LABS.keys()),
    )

    parser.add_argument(
        "--student",
        help=(
            "only grade this student_id "
            "from roster.csv"
        ),
    )

    parser.add_argument(
        "--notebook",
        help=(
            "only grade this notebook"
        ),
    )


    parser.add_argument(
        "--local-fixture",
        help=(
            "grade a local directory directly, "
            "bypassing git clone"
        ),
    )

    args = parser.parse_args()

    all_results = []

    # ========================================================
    # Local fixture
    # ========================================================

    if args.local_fixture:

        student_id = (
            args.student
            or "local_fixture"
        )

        workdir = Path(args.local_fixture).resolve()

        results = grade_student_lab(
            student_id,
            workdir,
            args.lab,
            notebook_filename=args.notebook,
        )

        all_results.extend(
            results
        )

    # ========================================================
    # Git repository mode
    # ========================================================

    else:

        roster = load_roster()

        # Filter by lab
        roster = [
            student
            for student in roster
            if student["lab"] == args.lab
        ]

        # Optional student filter
        if args.student:

            roster = [
                student
                for student in roster
                if student["student_id"]
                == args.student
            ]

        if not roster:

            print(
                f"No matching students for lab "
                f"'{args.lab}'"
                + (
                    f" and student "
                    f"'{args.student}'"
                    if args.student
                    else ""
                ),
                file=sys.stderr,
            )

            sys.exit(1)

        # ----------------------------------------------------
        # Grade students
        # ----------------------------------------------------

        for student in roster:

            with tempfile.TemporaryDirectory() as workdir:

                try:

                    fetch_submission(
                        student,
                        workdir,
                    )

                except RuntimeError as e:

                    print(
                        str(e),
                        file=sys.stderr,
                    )

                    all_results.append(
                        {
                            "student": student["student_id"],
                            "lab": args.lab,
                            "notebook": "submission",
                            "error": (
                                "MISSING_REPOSITORY: "
                                + str(e)
                            ),
                            "checks": [],
                            "score": 0.0,
                        }
                    )

                    continue

                results = grade_student_lab(
                    student["student_id"],
                    workdir,
                    args.lab,
                    notebook_filename=args.notebook,
                )

                all_results.extend(
                    results
                )

    # ========================================================
    # Print summary
    # ========================================================

    for result in all_results:

        error = result.get("error")

        if error == "notebook not found in submission":
            status = "MISSING"

        elif error and error.startswith("MISSING_REPOSITORY:"):
            status = "MISSING_REPOSITORY"

        elif error:
            status = "ERROR"

        else:
            status = f"{result['score'] * 100:.0f}%"

        print(
            f"{result['student']:20s} "
            f"{result['notebook']:30s} "
            f"{status}"
        )
    # ========================================================
    # Save results
    # ========================================================

    if all_results:

        write_results(
            all_results,
            args.lab,
        )

    else:

        print(
            "No grading results were produced.",
            file=sys.stderr,
        )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()