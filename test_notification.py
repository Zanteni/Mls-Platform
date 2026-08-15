import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = (
    Path(__file__).resolve().parent
    / "webapp"
    / "app.db"
)


connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()


cursor.execute(
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
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        5,
        3,
        14,
        "resubmission",
        "Test Notification",
        "This is a test notification for the notification system.",
        0,
        None,
        datetime.now(timezone.utc).isoformat(),
    ),
)


connection.commit()


rows = cursor.execute(
    """
    SELECT
        id,
        student_id,
        title,
        read
    FROM notifications
    ORDER BY id DESC
    """
).fetchall()


print("Notifications:")
for row in rows:
    print(row)


connection.close()