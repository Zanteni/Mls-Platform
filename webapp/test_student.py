from .database import SessionLocal
from .models import Student


with SessionLocal() as session:

    student = Student(
        github_username="wajdi-test",
        github_id="123456789",
        email="wajdi@example.com",
    )

    session.add(student)
    session.commit()

    print(
        f"Created student: "
        f"{student.id} / "
        f"{student.github_username}"
    )