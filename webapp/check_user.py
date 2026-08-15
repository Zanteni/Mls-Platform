from .database import SessionLocal
from .models import Student


with SessionLocal() as db:

    students = db.query(Student).all()

    for student in students:
        print(
            "ID:",
            student.id,
            "| GitHub:",
            student.github_username,
            "| Role:",
            student.role,
            "| Email:",
            student.email,
        )