"""
grading_worker.py

Runs one grading job outside the Flask process.

The worker does NOT access the application database.
It returns grading results to Flask as JSON.
"""

import argparse
import json
import sys

from grade import grade_submission


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Run one MLS lab grading job."
    )

    parser.add_argument(
        "--student-id",
        required=True,
    )

    parser.add_argument(
        "--lab-id",
        required=True,
    )

    parser.add_argument(
        "--snapshot-path",
        required=True,
    )

    parser.add_argument(
        "--submission-id",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--notebook",
        default=None,
    )

    args = parser.parse_args()


    # ========================================================
    # Run grading
    # ========================================================

    try:

        results = grade_submission(
            student_id=args.student_id,
            lab_id=args.lab_id,
            snapshot_path=args.snapshot_path,
            notebook_filename=args.notebook,
            submission_id=args.submission_id,
        )

    except Exception as exc:

        print(
            f"GRADING_ERROR: {exc}",
            file=sys.stderr,
        )

        return 1


    # ========================================================
    # Return result
    # ========================================================

    payload = {
        "success": True,
        "student_id": args.student_id,
        "lab_id": args.lab_id,
        "submission_id": args.submission_id,
        "results": results,
    }

    print(
        "GRADING_RESULT_JSON:"
        + json.dumps(
            payload,
            default=str,
        )
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )