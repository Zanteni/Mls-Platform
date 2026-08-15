from database import SessionLocal
from models import Student


with SessionLocal() as session:

    student = (
        session.query(Student)
        .filter_by(github_username="wajdi-test")
        .first()
    )

    print("Student:", student.github_username)

    for submission in student.submissions:
        print(
            "Lab:", submission.lab.name,
            "| Repo:", submission.repo_url,
            "| Status:", submission.status,
        )