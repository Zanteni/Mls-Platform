from .database import SessionLocal
from .models import (
    Student,
    Lab,
    Submission,
    Grade,
    NotebookResult,
    CheckResult,
)


def save_grading_result(result, submission_id=None):
    """
    Save one notebook-level grading result.

    If submission_id is provided, that exact submission is graded.

    Otherwise, fall back to the latest submission for compatibility
    with the existing CLI workflow.

    After saving the notebook result, the submission's automatic
    grade is recalculated from all currently available checks.

    Submission status is NOT changed here.
    The final submission status is handled by the grading workflow
    after all grading results have been processed.
    """

    # --------------------------------------------------
    # Basic information
    # --------------------------------------------------

    student_name = result["student"]
    lab_name = result["lab"]
    notebook_name = result["notebook"]

    # If submission_id was not explicitly passed, try to get it
    # from the grading result itself.
    if submission_id is None:
        submission_id = result.get("submission_id")

    with SessionLocal() as session:

        # --------------------------------------------------
        # Find student
        # --------------------------------------------------

        student = (
            session.query(Student)
            .filter_by(
                github_username=student_name
            )
            .first()
        )

        if student is None:
            raise ValueError(
                f"Student '{student_name}' not found."
            )

        # --------------------------------------------------
        # Find lab
        # --------------------------------------------------

        lab = (
            session.query(Lab)
            .filter_by(
                name=lab_name
            )
            .first()
        )

        if lab is None:
            raise ValueError(
                f"Lab '{lab_name}' not found."
            )

        # --------------------------------------------------
        # Find submission
        # --------------------------------------------------

        if submission_id is not None:

            submission = (
                session.query(Submission)
                .filter_by(
                    id=submission_id,
                    student_id=student.id,
                    lab_id=lab.id,
                )
                .first()
            )

        else:

            # Backward-compatible CLI behavior
            submission = (
                session.query(Submission)
                .filter_by(
                    student_id=student.id,
                    lab_id=lab.id,
                )
                .order_by(
                    Submission.submitted_at.desc()
                )
                .first()
            )

        if submission is None:
            raise ValueError(
                f"No submission found for "
                f"{student_name} / {lab_name}."
            )

        # --------------------------------------------------
        # Find or create overall grade
        # --------------------------------------------------

        grade = submission.grade

        if grade is None:

            grade = Grade(
                submission_id=submission.id,
                automatic_score=0.0,
            )

            session.add(grade)
            session.flush()

        # --------------------------------------------------
        # Find existing notebook result
        # --------------------------------------------------

        notebook_result = (
            session.query(NotebookResult)
            .filter_by(
                grade_id=grade.id,
                notebook_name=notebook_name,
            )
            .first()
        )

        if notebook_result is None:

            notebook_result = NotebookResult(
                grade_id=grade.id,
                notebook_name=notebook_name,
            )

            session.add(notebook_result)

        # --------------------------------------------------
        # Update notebook result
        # --------------------------------------------------

        notebook_result.score = result.get(
            "score",
            0.0,
        )

        notebook_result.error = result.get(
            "error"
        )

        session.flush()

        # --------------------------------------------------
        # Replace previous check results
        # --------------------------------------------------

        notebook_result.checks.clear()

        for check in result.get("checks", []):

            notebook_result.checks.append(
                CheckResult(
                    check_name=check["name"],
                    passed=check["passed"],
                    message=check.get("message"),
                )
            )

        session.flush()

        # --------------------------------------------------
        # Recalculate automatic grade
        # --------------------------------------------------

        notebooks = (
            session.query(NotebookResult)
            .filter_by(
                grade_id=grade.id
            )
            .all()
        )

        total_checks = sum(
            len(notebook.checks)
            for notebook in notebooks
        )

        total_passed = sum(
            sum(
                1
                for check in notebook.checks
                if check.passed
            )
            for notebook in notebooks
        )

        automatic_score = (
            100.0 * total_passed / total_checks
            if total_checks
            else 0.0
        )

        grade.automatic_score = automatic_score

        # --------------------------------------------------
        # IMPORTANT:
        # Do NOT update submission.status here.
        #
        # The submission status is handled by the outer
        # grading workflow / finalize_lab_grade().
        # --------------------------------------------------

        # --------------------------------------------------
        # Save everything
        # --------------------------------------------------

        session.commit()

        return notebook_result.id
    
def finalize_lab_grade(
    student_name,
    lab_name,
    submission_id=None,
):
    """
    Compute and store the overall automatic grade for a submission
    after all notebooks have been graded.

    If submission_id is provided, that exact submission is used.

    Otherwise, fall back to the latest submission for compatibility
    with the existing CLI workflow.
    """

    with SessionLocal() as session:

        # --------------------------------------------------
        # Find student
        # --------------------------------------------------

        student = (
            session.query(Student)
            .filter_by(
                github_username=student_name
            )
            .first()
        )

        if student is None:
            raise ValueError(
                f"Student '{student_name}' not found."
            )

        # --------------------------------------------------
        # Find lab
        # --------------------------------------------------

        lab = (
            session.query(Lab)
            .filter_by(
                name=lab_name
            )
            .first()
        )

        if lab is None:
            raise ValueError(
                f"Lab '{lab_name}' not found."
            )

        # --------------------------------------------------
        # Find submission
        # --------------------------------------------------

        if submission_id is not None:

            submission = (
                session.query(Submission)
                .filter_by(
                    id=submission_id,
                    student_id=student.id,
                    lab_id=lab.id,
                )
                .first()
            )

        else:

            # Backward-compatible CLI behavior
            submission = (
                session.query(Submission)
                .filter_by(
                    student_id=student.id,
                    lab_id=lab.id,
                )
                .order_by(
                    Submission.submitted_at.desc()
                )
                .first()
            )

        if submission is None:
            raise ValueError(
                f"No submission found for "
                f"{student_name} / {lab_name}."
            )

        # --------------------------------------------------
        # Grade must exist
        # --------------------------------------------------

        if submission.grade is None:
            raise ValueError(
                "No grade exists for this submission."
            )

        # --------------------------------------------------
        # Get notebook results
        # --------------------------------------------------

        notebooks = submission.grade.notebooks

        if not notebooks:
            raise ValueError(
                "No notebook results found."
            )

        # --------------------------------------------------
        # Calculate overall score
        # --------------------------------------------------

        total_checks = sum(
            len(notebook.checks)
            for notebook in notebooks
        )

        total_passed = sum(
            sum(
                1
                for check in notebook.checks
                if check.passed
            )
            for notebook in notebooks
        )

        automatic_score = (
            100.0 * total_passed / total_checks
            if total_checks
            else 0.0
        )

        # --------------------------------------------------
        # Store automatic grade
        # --------------------------------------------------

        submission.grade.automatic_score = (
            automatic_score
        )

        # --------------------------------------------------
        # Update submission status
        # --------------------------------------------------

        submission.status = "graded"

        # --------------------------------------------------
        # Commit
        # --------------------------------------------------

        session.commit()

        return automatic_score