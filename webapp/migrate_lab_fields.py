import sqlite3
from pathlib import Path


# ============================================================
# Database location
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)

DB_PATH = BASE_DIR / "app.db"


# ============================================================
# Columns to add
# ============================================================

NEW_COLUMNS = {
    "slug": "VARCHAR(150)",
    "display_order": "INTEGER NOT NULL DEFAULT 0",
    "category": "VARCHAR(100)",
    "archived": "BOOLEAN NOT NULL DEFAULT 0",
    "visible": "BOOLEAN NOT NULL DEFAULT 1",
    "solution_url": "VARCHAR(1000)",
    "video_url": "VARCHAR(1000)",
    "teacher_notes": "TEXT",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}


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
        # Inspect existing columns
        # ----------------------------------------------------

        cursor.execute(
            "PRAGMA table_info(labs)"
        )

        existing_columns = {
            row[1]
            for row in cursor.fetchall()
        }

        print("Existing Lab columns:")

        for column in sorted(existing_columns):
            print(f"  - {column}")

        # ----------------------------------------------------
        # Add missing columns
        # ----------------------------------------------------

        for column, sql_type in NEW_COLUMNS.items():

            if column in existing_columns:

                print(
                    f"[SKIP] {column} already exists."
                )

                continue

            sql = (
                f"ALTER TABLE labs "
                f"ADD COLUMN {column} {sql_type}"
            )

            print(
                f"[ADD] {column}"
            )

            cursor.execute(sql)

        # ----------------------------------------------------
        # Populate timestamps for existing labs
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE labs
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )

        cursor.execute(
            """
            UPDATE labs
            SET updated_at = CURRENT_TIMESTAMP
            WHERE updated_at IS NULL
            """
        )

        # ----------------------------------------------------
        # Generate initial slugs
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id, name, slug
            FROM labs
            ORDER BY id
            """
        )

        labs = cursor.fetchall()

        for lab_id, name, slug in labs:

            if slug:
                continue

            base_slug = (
                name.strip()
                .lower()
            )

            # Basic slug conversion
            import re

            base_slug = re.sub(
                r"[^a-z0-9]+",
                "-",
                base_slug,
            ).strip("-")

            if not base_slug:
                base_slug = f"lab-{lab_id}"

            # Ensure uniqueness
            candidate = base_slug
            counter = 2

            while True:

                cursor.execute(
                    """
                    SELECT id
                    FROM labs
                    WHERE slug = ?
                    AND id != ?
                    """,
                    (
                        candidate,
                        lab_id,
                    ),
                )

                exists = cursor.fetchone()

                if not exists:
                    break

                candidate = (
                    f"{base_slug}-{counter}"
                )

                counter += 1

            cursor.execute(
                """
                UPDATE labs
                SET slug = ?
                WHERE id = ?
                """,
                (
                    candidate,
                    lab_id,
                ),
            )

            print(
                f"[SLUG] Lab {lab_id}: {candidate}"
            )

        # ----------------------------------------------------
        # Initial display order
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM labs
            ORDER BY id
            """
        )

        lab_ids = [
            row[0]
            for row in cursor.fetchall()
        ]

        for index, lab_id in enumerate(
            lab_ids,
            start=1,
        ):

            cursor.execute(
                """
                UPDATE labs
                SET display_order = ?
                WHERE id = ?
                """,
                (
                    index,
                    lab_id,
                ),
            )

        connection.commit()

        print()
        print(
            "Lab migration completed successfully."
        )

    except Exception:

        connection.rollback()

        print(
            "Migration failed. "
            "All changes were rolled back."
        )

        raise

    finally:

        connection.close()


if __name__ == "__main__":
    migrate()