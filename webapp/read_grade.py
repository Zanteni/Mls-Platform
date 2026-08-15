from .database import SessionLocal
from .models import Student, Lab, Submission


with SessionLocal() as session:

    student = (
        session.query(Student)
        .filter_by(github_username="wajdi")
        .first()
    )

    lab = (
        session.query(Lab)
        .filter_by(name="lab3")
        .first()
    )

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
        print("No submission found.")
        raise SystemExit

    grade = submission.grade

    print("Student:", student.github_username)
    print("Lab:", lab.name)
    print("Repository:", submission.repo_url)
    print("Status:", submission.status)
    print("Automatic score:", grade.automatic_score)

    print("\nNotebooks:")

    for notebook in grade.notebooks:

        print(
            f"\nNotebook: {notebook.notebook_name}"
        )

        print(
            f"Score: {notebook.score * 100:.1f}%"
        )

        if notebook.error:
            print(
                f"Error: {notebook.error}"
            )

        for check in notebook.checks:

            status = (
                "PASS"
                if check.passed
                else "FAIL"
            )

            print(
                f"  {status:5s} "
                f"{check.check_name}: "
                f"{check.message}"
            )