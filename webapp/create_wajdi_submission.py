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

    existing = (
        session.query(Submission)
        .filter_by(
            student_id=student.id,
            lab_id=lab.id,
        )
        .first()
    )

    if existing is None:

        submission = Submission(
            student_id=student.id,
            lab_id=lab.id,
            repo_url=(
                "https://github.com/MLs-labs/"
                "wajdi-lab-3.git"
            ),
            status="submitted",
        )

        session.add(submission)
        session.commit()

        print(
            f"Created submission: "
            f"{submission.id}"
        )

    else:

        print(
            f"Submission already exists: "
            f"{existing.id}"
        )