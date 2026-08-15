import sqlite3
from pathlib import Path


# ============================================================
# Database
# ============================================================

DB_PATH = (
    Path(__file__)
    .resolve()
    .parent
    / "app.db"
)


# ============================================================
# Migration
# ============================================================

def migrate():

    if not DB_PATH.exists():

        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    try:

        # ----------------------------------------------------
        # Check whether table already exists
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name='notifications'
            """
        )

        exists = cursor.fetchone()

        if exists:

            print(
                "notifications table already exists."
            )

            return

        # ----------------------------------------------------
        # Create table
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE notifications (

                id INTEGER PRIMARY KEY,

                student_id INTEGER NOT NULL,

                lab_id INTEGER,

                submission_id INTEGER,

                notification_type VARCHAR(50) NOT NULL,

                title VARCHAR(200) NOT NULL,

                message TEXT NOT NULL,

                read BOOLEAN NOT NULL DEFAULT 0,

                read_at DATETIME,

                created_at DATETIME,

                FOREIGN KEY(student_id)
                    REFERENCES students(id),

                FOREIGN KEY(lab_id)
                    REFERENCES labs(id),

                FOREIGN KEY(submission_id)
                    REFERENCES submissions(id)
            )
            """
        )

        # ----------------------------------------------------
        # Indexes
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX
            ix_notifications_student_id
            ON notifications(student_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX
            ix_notifications_read
            ON notifications(read)
            """
        )

        cursor.execute(
            """
            CREATE INDEX
            ix_notifications_created_at
            ON notifications(created_at)
            """
        )

        connection.commit()

        print(
            "Notifications migration completed successfully."
        )

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


if __name__ == "__main__":
    migrate()