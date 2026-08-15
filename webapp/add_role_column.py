from sqlalchemy import text

from .database import engine


with engine.begin() as connection:

    connection.execute(
        text(
            """
            ALTER TABLE students
            ADD COLUMN role VARCHAR(20)
            NOT NULL
            DEFAULT 'student'
            """
        )
    )

print("Role column added successfully.")