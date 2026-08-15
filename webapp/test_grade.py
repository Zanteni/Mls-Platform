from .database import SessionLocal
from .models import Submission, Grade, CheckResult


with SessionLocal() as session:

    submission = (
        session.query(Submission)
        .first()
    )

    grade = Grade(
        submission_id=submission.id,
        automatic_score=100.0,
        teacher_score=None,
        feedback=None,
    )

    session.add(grade)
    session.flush()

    checks = [
        CheckResult(
            grade_id=grade.id,
            check_name="kernel_matrix",
            passed=True,
            message="All tests passed!",
        ),
        CheckResult(
            grade_id=grade.id,
            check_name="dual_objective",
            passed=True,
            message="All tests passed!",
        ),
        CheckResult(
            grade_id=grade.id,
            check_name="alpha_constraints",
            passed=True,
            message="All tests passed!",
        ),
        CheckResult(
            grade_id=grade.id,
            check_name="training",
            passed=False,
            message="Training accuracy below threshold.",
        ),
    ]

    session.add_all(checks)
    session.commit()

    print(f"Grade created: {grade.id}")
    print(f"Automatic score: {grade.automatic_score}")