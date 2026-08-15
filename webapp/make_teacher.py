
from .database import SessionLocal
from .models import Student


with SessionLocal() as db:

    student = (
        db.query(Student)
        .filter_by(
            github_username="Zanteni"
        )
        .first()
    )

    if student is None:

        print("Student not found.")

    else:

        student.role = "teacher"

        db.commit()

        print(
            f"{student.github_username} is now a {student.role}."
        )
