from .database import SessionLocal
from .models import Student, Lab, Submission


with SessionLocal() as session:

    student = (
        session.query(Student)
        .filter_by(github_username="wajdi-test")
        .first()
    )

    lab = (
        session.query(Lab)
        .filter_by(name="lab3")
        .first()
    )

    submission = Submission(
        student_id=student.id,
        lab_id=lab.id,
        repo_url="https://github.com/MLs-labs/wajdi-lab-3.git",
        status="submitted",
    )

    session.add(submission)
    session.commit()

    print(
        f"Submission created: "
        f"{submission.id}"
    )