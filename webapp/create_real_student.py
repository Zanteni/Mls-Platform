from .database import SessionLocal
from .models import Student

with SessionLocal() as session:

    existing = (
        session.query(Student)
        .filter_by(github_username="wajdi")
        .first()
    )

    if existing is None:

        student = Student(
            github_username="wajdi",
            github_id="test-wajdi",
            email="wajdi@example.com",
        )

        session.add(student)
        session.commit()

        print(
            f"Created student: "
            f"{student.id} / {student.github_username}"
        )

    else:
        print(
            f"Student already exists: "
            f"{existing.id} / {existing.github_username}"
        )