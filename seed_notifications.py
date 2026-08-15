import sqlite3
from datetime import datetime
from pathlib import Path
from datetime import datetime, timezone

now = datetime.now(timezone.utc).isoformat()

# ============================================================
# Database Path
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

DB_PATH = PROJECT_ROOT / "webapp" / "app.db"


print("Using database:")
print(DB_PATH)

if not DB_PATH.exists():

    raise FileNotFoundError(
        f"Database not found: {DB_PATH}"
    )


connection = sqlite3.connect(DB_PATH)

cursor = connection.cursor()

# ------------------------------------------------------------
# Check students
# ------------------------------------------------------------

students = cursor.execute(
    """
    SELECT id, github_username
    FROM students
    ORDER BY id
    """
).fetchall()

print("Students:")
for student in students:
    print(student)


# ------------------------------------------------------------
# Change this to the student you want to test with
# ------------------------------------------------------------

TEST_STUDENT_ID = 5


# ------------------------------------------------------------
# Create test notifications
# ------------------------------------------------------------

now = datetime.utcnow().isoformat()


notifications = [

    (
        TEST_STUDENT_ID,
        3,
        14,
        "resubmission",
        "Resubmission Request Rejected",
        (
            "Your resubmission request was rejected by the teacher. "
            "You have 2 rejection requests remaining."
        ),
        0,
        None,
        now,
    ),

    (
        TEST_STUDENT_ID,
        3,
        14,
        "grade",
        "Grade Published",
        (
            "Your final grade for Lab 3 has been published. "
            "Your final score is 87.50/100."
        ),
        0,
        None,
        now,
    ),

    (
        TEST_STUDENT_ID,
        1,
        None,
        "announcement",
        "New Lab Available",
        "Lab 1 is now available for submission.",
        0,
        None,
        now,
    ),

]


cursor.executemany(
    """
    INSERT INTO notifications (
        student_id,
        lab_id,
        submission_id,
        notification_type,
        title,
        message,
        read,
        read_at,
        created_at
    )
    VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?
    )
    """,
    notifications,
)


connection.commit()


# ------------------------------------------------------------
# Show inserted notifications
# ------------------------------------------------------------

rows = cursor.execute(
    """
    SELECT
        id,
        student_id,
        notification_type,
        title,
        read,
        created_at
    FROM notifications
    ORDER BY id DESC
    """
).fetchall()


print("\nNotifications:")
for row in rows:
    print(row)


connection.close()


print("\nDone.")