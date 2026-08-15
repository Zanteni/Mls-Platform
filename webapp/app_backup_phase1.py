
import os
import re
import smtplib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    abort,
    flash,
)
import shutil
import subprocess
from pathlib import Path
from webapp.email_utils import send_grade_published_email
from werkzeug.middleware.proxy_fix import ProxyFix
from grade import grade_submission
from authlib.integrations.flask_client import OAuth
from sqlalchemy.orm import joinedload

from .database import SessionLocal
from .models import (
    Lab,
    Student,
    Submission,
    Grade,
    NotebookResult,
)
MAX_SUBMISSION_ATTEMPTS = 3
MAX_RESUBMISSION_REJECTIONS = 3
load_dotenv()
#helper 
def ensure_utc(dt):
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(timezone.utc)

# ============================================================
# Repository Snapshot
# ============================================================

def create_repository_snapshot(
    repo_url,
    submission_id,
):
    root = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    snapshot_root = (
        root
        / "data"
        / "submissions"
        / str(submission_id)
    )

    repo_path = snapshot_root / "repo"

    if snapshot_root.exists():
        shutil.rmtree(snapshot_root)

    snapshot_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                repo_url,
                str(repo_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        commit_sha = result.stdout.strip()

        return (
            str(repo_path),
            commit_sha,
        )

    except Exception:
        if snapshot_root.exists():
            shutil.rmtree(snapshot_root)

        raise
# ============================================================
# Authentication decorators
# ============================================================

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "student_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def teacher_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "student_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "teacher":
            return abort(403)
        return view(*args, **kwargs)
    return wrapped_view


# ============================================================
# Flask application
# ============================================================

app = Flask(__name__)
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
)

# ============================================================
# Flask session security
# ============================================================

app.secret_key = os.environ["FLASK_SECRET_KEY"]

# ============================================================
# GitHub OAuth
# ============================================================

oauth = OAuth(app)

github = oauth.register(
    name="github",
    client_id=os.environ["GITHUB_CLIENT_ID"],
    client_secret=os.environ["GITHUB_CLIENT_SECRET"],
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    api_base_url="https://api.github.com/",
    client_kwargs={
        "scope": "read:user user:email",
    },
)

# ============================================================
# Helpers
# ============================================================

def clean_terminal_text(text):
    if not text:
        return text
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ============================================================
# Email
# ============================================================

def send_grade_email(
    student_email,
    student_username,
    lab_name,
    teacher_score,
    feedback,
):
    """
    Legacy local SMTP helper.
    Publication routes currently use
    send_grade_published_email from webapp.email_utils.
    """
    if not student_email:
        return False

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(
        os.environ.get(
            "SMTP_PORT",
            "587",
        )
    )
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    sender_email = os.environ.get(
        "MAIL_FROM",
        smtp_username,
    )

    missing = []

    if not smtp_host:
        missing.append("SMTP_HOST")
    if not smtp_username:
        missing.append("SMTP_USERNAME")
    if not smtp_password:
        missing.append("SMTP_PASSWORD")
    if not sender_email:
        missing.append("MAIL_FROM")

    if missing:
        raise RuntimeError(
            "Missing SMTP environment variables: "
            + ", ".join(missing)
        )

    message = EmailMessage()
    message["Subject"] = f"Grade published — {lab_name}"
    message["From"] = sender_email
    message["To"] = student_email

    feedback_text = (
        feedback
        if feedback
        else "No feedback provided."
    )

    message.set_content(
        f"""
Hello {student_username},

Your grade for the lab "{lab_name}" has been published.

Teacher grade: {teacher_score:.2f}%

Feedback:

{feedback_text}

Please log in to the Lab Grading System
to view your complete submission and results.

Best regards,
Lab Grading System
""".strip()
    )

    with smtplib.SMTP(
        smtp_host,
        smtp_port,
        timeout=20,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(
            smtp_username,
            smtp_password,
        )
        smtp.send_message(message)

    return True


# ============================================================
# Home
# ============================================================

@app.route("/")
def home():
    with SessionLocal() as db:
        labs = (
            db.query(Lab)
            .order_by(Lab.id)
            .all()
        )
        return render_template(
            "home.html",
            labs=labs,
        )


# ============================================================
# Lab page
# ============================================================

@app.route("/lab/<int:lab_id>")
@login_required
def lab_page(lab_id):
    with SessionLocal() as db:
        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        now = datetime.now(timezone.utc)

        if lab.submission_deadline is not None:
            lab.submission_deadline = ensure_utc(
                lab.submission_deadline
            )
        query = (
            db.query(Submission)
            .options(
                joinedload(Submission.student),
                joinedload(Submission.grade),
            )
            .filter_by(
                lab_id=lab.id
            )
        )

        if session.get("role") != "teacher":
            query = query.filter(
                Submission.student_id
                == session["student_id"]
            )

        submissions = (
            query
            .order_by(
                Submission.submitted_at.desc()
            )
            .all()
        )

        return render_template(
            "lab.html",
            lab=lab,
            submissions=submissions,
            now=now,
        )


# ============================================================
# Lab submission
# ============================================================



@app.route(
    "/lab/<int:lab_id>/submit",
    methods=["POST"],
)
@login_required
def submit_lab(lab_id):

    repo_url = request.form.get(
        "repo_url",
        "",
    ).strip()

    # --------------------------------------------------------
    # Validate repository URL
    # --------------------------------------------------------

    if not repo_url:

        return (
            "Repository URL is required.",
            400,
        )

    if not repo_url.startswith(
        "https://github.com/"
    ):

        return (
            "Please provide a valid GitHub repository URL.",
            400,
        )

    with SessionLocal() as db:

        # ----------------------------------------------------
        # Load lab
        # ----------------------------------------------------

        lab = (
            db.query(Lab)
            .filter_by(
                id=lab_id
            )
            .first()
        )

        if lab is None:

            return (
                "Lab not found",
                404,
            )

        # ----------------------------------------------------
        # Lab must be launched
        # ----------------------------------------------------

        if not lab.launched:

            return (
                "This laboratory has not been launched yet.",
                403,
            )

        # ----------------------------------------------------
        # Get student
        # ----------------------------------------------------

        student = (
            db.query(Student)
            .filter_by(
                id=session["student_id"]
            )
            .first()
        )

        if student is None:

            session.clear()

            return redirect(
                url_for("login")
            )

        # ----------------------------------------------------
        # Find current submission
        # ----------------------------------------------------

        current_submission = (
            db.query(Submission)
            .filter_by(
                student_id=student.id,
                lab_id=lab.id,
                is_current=True,
            )
            .order_by(
                Submission.attempt_number.desc()
            )
            .first()
        )

        # ====================================================
        # DETERMINE SUBMISSION TYPE
        # ====================================================

        # ----------------------------------------------------
        # First submission
        # ----------------------------------------------------

        if current_submission is None:

            is_resubmission = False
            attempt_number = 1

        # ----------------------------------------------------
        # Existing submission
        # ----------------------------------------------------

        else:

            is_resubmission = (
                current_submission.resubmission_allowed
            )

            # -----------------------------------------------
            # Maximum attempts
            # -----------------------------------------------

            if (
                current_submission.attempt_number
                >= MAX_SUBMISSION_ATTEMPTS
            ):

                flash(
                    f"You have reached the maximum of "
                    f"{MAX_SUBMISSION_ATTEMPTS} attempts for this lab.",
                    "warning",
                )

                return redirect(
                    url_for(
                        "lab_page",
                        lab_id=lab.id,
                    )
                )

            # -----------------------------------------------
            # Resubmission must be approved
            # -----------------------------------------------

            if not is_resubmission:

                return (
                    "You have already submitted this lab. "
                    "Please request permission from the teacher "
                    "to resubmit.",
                    403,
                )

            attempt_number = (
                current_submission.attempt_number + 1
            )

        # ====================================================
        # NORMAL SUBMISSION WINDOW
        # ====================================================

        # First submission must obey the lab's normal
        # submission window and deadline.
        #
        # Teacher-approved resubmissions are exceptions
        # and can be submitted after the normal window closes.

        if not is_resubmission:

            now = datetime.now(timezone.utc)

            deadline = ensure_utc(
                lab.submission_deadline
            )

            # -----------------------------------------------
            # Manual close
            # -----------------------------------------------

            if not lab.submission_open:

                return (
                    "Submissions are currently closed for this lab.",
                    403,
                )

            # -----------------------------------------------
            # Deadline
            # -----------------------------------------------

            if (
                deadline is not None
                and now >= deadline
            ):

                return (
                    "The submission deadline for this lab has passed.",
                    403,
                )

        # ====================================================
        # CREATE NEW SUBMISSION
        # ====================================================

        submission = Submission(
            student_id=student.id,
            lab_id=lab.id,
            repo_url=repo_url,
            status="submitted",
            attempt_number=attempt_number,
            snapshot_path=None,
            commit_sha=None,
            is_current=True,
            resubmission_allowed=False,
            resubmission_requested=False,
            resubmission_message=None,
        )

        db.add(submission)

        # We need the submission ID before creating
        # the immutable snapshot directory.

        db.flush()

        # ====================================================
        # CREATE IMMUTABLE SNAPSHOT
        # ====================================================

        try:

            snapshot_path, commit_sha = (
                create_repository_snapshot(
                    repo_url=repo_url,
                    submission_id=submission.id,
                )
            )

        except Exception as e:

            # Roll back the database transaction.
            #
            # If this was a resubmission, the previous
            # submission remains current.

            db.rollback()

            app.logger.exception(
                "Failed to create repository snapshot "
                "for submission %s",
                submission.id,
            )

            return (
                "Could not create a snapshot of the "
                "repository. Please verify that the "
                "repository is accessible and try again.",
                500,
            )

        # ====================================================
        # Previous current submission becomes historical
        # ====================================================

        if current_submission is not None:

            current_submission.is_current = False

            current_submission.resubmission_allowed = False

            current_submission.resubmission_requested = False

            current_submission.resubmission_message = None

        # ====================================================
        # Save snapshot information
        # ====================================================

        submission.snapshot_path = (
            snapshot_path
        )

        submission.commit_sha = (
            commit_sha
        )

        db.commit()

        db.refresh(submission)

        app.logger.info(
            "Submission %s created successfully. "
            "Attempt=%s Commit=%s Snapshot=%s",
            submission.id,
            submission.attempt_number,
            submission.commit_sha,
            submission.snapshot_path,
        )

        return redirect(
            url_for(
                "submission_page",
                submission_id=submission.id,
            )
        )



# ============================================================
# Student submission page
# ============================================================

@app.route(
    "/submission/<int:submission_id>"
)
@login_required
def submission_page(submission_id):
    with SessionLocal() as db:
        submission = (
            db.query(Submission)
            .options(
                joinedload(Submission.student),
                joinedload(
                    Submission.grade
                )
                .selectinload(
                    Grade.notebooks
                )
                .selectinload(
                    NotebookResult.checks
                ),
            )
            .filter_by(id=submission_id)
            .first()
        )

        if submission is None:
            return (
                "Submission not found",
                404,
            )

        if (
            session.get("role") != "teacher"
            and submission.student_id
            != session["student_id"]
        ):
            return abort(403)

        if submission.grade:
            for notebook in submission.grade.notebooks:
                for check in notebook.checks:
                    check.message = clean_terminal_text(
                        check.message
                    )

        return render_template(
            "submission.html",
            submission=submission,
        )

#reject allsubmm 
@app.route(
    "/teacher/lab/<int:lab_id>/reject-resubmit-all",
    methods=["POST"],
)
@teacher_required
def reject_resubmit_all(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        submissions = (
            db.query(Submission)
            .filter_by(
                lab_id=lab.id,
                is_current=True,
                resubmission_requested=True,
            )
            .all()
        )

        rejected_count = 0

        for submission in submissions:

            submission.resubmission_requested = False
            submission.resubmission_allowed = False
            submission.resubmission_rejections += 1

            if (
                submission.resubmission_rejections
                >= MAX_RESUBMISSION_REJECTIONS
            ):

                submission.resubmission_message = (
                    f"Your resubmission request has been rejected "
                    f"{MAX_RESUBMISSION_REJECTIONS} times. "
                    "No further resubmission requests are allowed "
                    "for this attempt."
                )

            else:

                remaining = (
                    MAX_RESUBMISSION_REJECTIONS
                    - submission.resubmission_rejections
                )

                submission.resubmission_message = (
                    "Your resubmission request was rejected "
                    "by the teacher. "
                    f"You have {remaining} rejection request"
                    f"{'s' if remaining != 1 else ''} remaining."
                )

            rejected_count += 1

        db.commit()

        app.logger.info(
            "Rejected %s resubmission requests for lab %s",
            rejected_count,
            lab.id,
        )

        return redirect(
            url_for(
                "lab_page",
                lab_id=lab.id,
            )
        )
# ============================================================
# Teacher grading page
# ============================================================

@app.route(
    "/teacher/submission/<int:submission_id>",
    methods=["GET", "POST"],
)
@teacher_required
def teacher_submission_page(submission_id):
    with SessionLocal() as db:
        submission = (
            db.query(Submission)
            .options(
                joinedload(Submission.student),
                joinedload(Submission.lab),
                joinedload(
                    Submission.grade
                )
                .selectinload(
                    Grade.notebooks
                )
                .selectinload(
                    NotebookResult.checks
                ),
            )
            .filter_by(id=submission_id)
            .first()
        )

        if submission is None:
            return (
                "Submission not found",
                404,
            )

        if submission.grade is None:
            grade = Grade(
                submission_id=submission.id,
                automatic_score=None,
                teacher_score=None,
                feedback=None,
                published_at=None,
            )
            db.add(grade)
            db.commit()
            db.refresh(grade)
            submission.grade = grade
        else:
            grade = submission.grade

        if request.method == "POST":
            teacher_score = request.form.get(
                "teacher_score",
                type=float,
            )

            feedback = request.form.get(
                "feedback",
                "",
            ).strip()

            action = request.form.get("action")

            if teacher_score is None:
                return (
                    "Teacher score is required.",
                    400,
                )

            if not 0 <= teacher_score <= 100:
                return (
                    "Teacher score must be between 0 and 100.",
                    400,
                )

            if action == "save":
                grade.teacher_score = teacher_score
                grade.feedback = feedback
                db.commit()

                return redirect(
                    url_for(
                        "teacher_submission_page",
                        submission_id=submission.id,
                    )
                )

            if action == "publish":
                if submission.status not in (
                    "graded",
                    "published",
                ):
                    return (
                        "This submission must be graded before "
                        "it can be published.",
                        400,
                    )

                if grade.automatic_score is None:
                    return (
                        "Automatic grading must be completed "
                        "before publishing.",
                        400,
                    )

                final_score = (
                    0.7 * grade.automatic_score
                    + 0.3 * teacher_score
                )

                grade.teacher_score = teacher_score
                grade.feedback = feedback

                first_publication = (
                    grade.published_at is None
                )

                if first_publication:
                    grade.published_at = (
                        datetime.now(timezone.utc)
                    )

                submission.status = "published"

                db.commit()

                email_sent = False
                email_error = False

                if (
                    first_publication
                    and submission.student.email
                ):
                    try:
                        email_sent = (
                            send_grade_published_email(
                                student_email=(
                                    submission.student.email
                                ),
                                student_username=(
                                    submission.student.github_username
                                ),
                                lab_name=(
                                    submission.lab.name
                                ),
                                score=final_score,
                                feedback=feedback,
                            )
                        )
                    except Exception as e:
                        email_error = True
                        app.logger.exception(
                            "Failed to send grade email: %s",
                            e,
                        )

                for notebook in grade.notebooks:
                    for check in notebook.checks:
                        check.message = clean_terminal_text(
                            check.message
                        )

                return render_template(
                    "teacher_submission.html",
                    submission=submission,
                    email_sent=email_sent,
                    email_error=email_error,
                )

            return (
                "Invalid action.",
                400,
            )

        for notebook in grade.notebooks:
            for check in notebook.checks:
                check.message = clean_terminal_text(
                    check.message
                )

        return render_template(
            "teacher_submission.html",
            submission=submission,
            email_sent=False,
            email_error=False,
        )


# ============================================================
# Grade One Submission
# ============================================================

@app.route(
    "/teacher/submission/<int:submission_id>/grade",
    methods=["POST"],
)
@teacher_required
def grade_entire_submission(submission_id):
    #here 
    with SessionLocal() as db:

        submission = (
            db.query(Submission)
            .options(
                joinedload(Submission.student),
                joinedload(Submission.lab),
            )
            .filter_by(
                id=submission_id
            )
            .first()
        )

        if submission is None:
            return (
                "Submission not found",
                404,
            )

        student_username = (
            submission.student.github_username
        )

        lab_name = submission.lab.name

        snapshot_path = submission.snapshot_path

    try:
        if not submission.snapshot_path:
            return (
                "This submission has no frozen repository snapshot. "
                "It cannot be graded.",
                400,
            )
        grade_submission(
        student_id=student_username,
        snapshot_path=submission.snapshot_path,
        lab_id=lab_name,
        submission_id=submission.id,
    )
    except Exception as e:
        app.logger.exception(
            "Grading failed for submission %s",
            submission_id,
        )

        with SessionLocal() as db:
            submission = (
                db.query(Submission)
                .filter_by(id=submission_id)
                .first()
            )

            if submission:
                submission.status = "grading_error"
                db.commit()

        return (
            f"Grading failed: {e}",
            500,
        )

    with SessionLocal() as db:
        submission = (
            db.query(Submission)
            .filter_by(id=submission_id)
            .first()
        )

        if submission is None:
            return (
                "Submission not found after grading.",
                404,
            )

        submission.status = "graded"
        db.commit()

        app.logger.info(
            "Submission %s successfully graded. "
            "Status changed to 'graded'.",
            submission_id,
        )

    return redirect(
        url_for(
            "teacher_submission_page",
            submission_id=submission_id,
        )
    )

# ============================================================
# Student resubmission Requist 
# ============================================================
@app.route(
    "/submission/<int:submission_id>/request-resubmit",
    methods=["POST"],
)
@login_required
def request_resubmission(submission_id):
    with SessionLocal() as db:
        submission = (
            db.query(Submission)
            .filter_by(id=submission_id)
            .first()
        )

        if submission is None:
            return "Submission not found", 404

        if submission.student_id != session["student_id"]:
            return abort(403)

        if not submission.is_current:
            return (
                "Only the current submission can request a resubmission.",
                400,
            )

        # ----------------------------------------------------
        # Maximum attempts reached
        # ----------------------------------------------------

        if submission.attempt_number >= MAX_SUBMISSION_ATTEMPTS:
            submission.resubmission_requested = False
            submission.resubmission_allowed = False
            submission.resubmission_message = (
                f"You have already reached the maximum of "
                f"{MAX_SUBMISSION_ATTEMPTS} attempts for this lab."
            )
            db.commit()

            flash(
                f"You have reached the maximum of "
                f"{MAX_SUBMISSION_ATTEMPTS} attempts for this lab.",
                "warning",
            )

            return redirect(
                url_for(
                    "lab_page",
                    lab_id=submission.lab_id,
                )
            )

        # ----------------------------------------------------
        # Teacher manually blocked resubmission requests
        # ----------------------------------------------------

        if submission.resubmission_blocked:
            submission.resubmission_requested = False
            submission.resubmission_allowed = False
            submission.resubmission_message = (
                "Resubmission requests are currently blocked "
                "by the teacher."
            )
            db.commit()

            flash(
                "Resubmission requests are currently blocked by the teacher.",
                "warning",
            )

            return redirect(
                url_for(
                    "lab_page",
                    lab_id=submission.lab_id,
                )
            )

        # ----------------------------------------------------
        # Maximum rejected requests
        # ----------------------------------------------------

        if (
            submission.resubmission_rejections
            >= MAX_RESUBMISSION_REJECTIONS
        ):
            submission.resubmission_requested = False
            submission.resubmission_allowed = False
            submission.resubmission_message = (
                f"Your resubmission request has been rejected "
                f"{MAX_RESUBMISSION_REJECTIONS} times. "
                "No further resubmission requests are allowed "
                "for this attempt."
            )
            db.commit()

            flash(
                "You have reached the maximum number of "
                "rejected resubmission requests.",
                "warning",
            )

            return redirect(
                url_for(
                    "lab_page",
                    lab_id=submission.lab_id,
                )
            )

        # ----------------------------------------------------
        # Already approved
        # ----------------------------------------------------

        if submission.resubmission_allowed:
            flash(
                "A resubmission has already been approved.",
                "info",
            )

            return redirect(
                url_for(
                    "lab_page",
                    lab_id=submission.lab_id,
                )
            )

        # ----------------------------------------------------
        # Request already pending
        # ----------------------------------------------------

        if submission.resubmission_requested:
            flash(
                "Your resubmission request is already pending.",
                "info",
            )

            return redirect(
                url_for(
                    "lab_page",
                    lab_id=submission.lab_id,
                )
            )

        # ----------------------------------------------------
        # Create request
        # ----------------------------------------------------

        submission.resubmission_requested = True
        submission.resubmission_allowed = False
        submission.resubmission_message = None

        db.commit()

        flash(
            "Your resubmission request has been sent to the teacher.",
            "success",
        )

        return redirect(
            url_for(
                "lab_page",
                lab_id=submission.lab_id,
            )
        )

#block 
@app.route(
    "/teacher/submission/<int:submission_id>/block-resubmit",
    methods=["POST"],
)
@teacher_required
def block_resubmission(submission_id):

    with SessionLocal() as db:

        submission = (
            db.query(Submission)
            .filter_by(id=submission_id)
            .first()
        )

        if submission is None:
            return "Submission not found", 404

        if not submission.is_current:
            return (
                "Only the current submission can be modified.",
                400,
            )

        submission.resubmission_blocked = True
        submission.resubmission_requested = False
        submission.resubmission_allowed = False
        submission.resubmission_message = (
            "Resubmission requests have been blocked by the teacher."
        )

        db.commit()

        return redirect(
            url_for(
                "lab_page",
                lab_id=submission.lab_id,
            )
        )

#unblock one student 

@app.route(
    "/teacher/submission/<int:submission_id>/unblock-resubmit",
    methods=["POST"],
)
@teacher_required
def unblock_resubmission(submission_id):

    with SessionLocal() as db:

        submission = (
            db.query(Submission)
            .filter_by(id=submission_id)
            .first()
        )

        if submission is None:
            return "Submission not found", 404

        if not submission.is_current:
            return (
                "Only the current submission can be modified.",
                400,
            )

        submission.resubmission_blocked = False
        submission.resubmission_message = (
            "Resubmission requests have been re-enabled by the teacher."
        )

        db.commit()

        return redirect(
            url_for(
                "lab_page",
                lab_id=submission.lab_id,
            )
        )

#block all 
@app.route(
    "/teacher/lab/<int:lab_id>/block-resubmit-all",
    methods=["POST"],
)
@teacher_required
def block_resubmit_all(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        submissions = (
            db.query(Submission)
            .filter_by(
                lab_id=lab.id,
                is_current=True,
            )
            .all()
        )

        for submission in submissions:
            submission.resubmission_blocked = True
            submission.resubmission_requested = False
            submission.resubmission_allowed = False
            submission.resubmission_message = (
                "Resubmission requests have been blocked by the teacher."
            )

        db.commit()

        return redirect(
            url_for(
                "lab_page",
                lab_id=lab.id,
            )
        )
#unblock alll
@app.route(
    "/teacher/lab/<int:lab_id>/unblock-resubmit-all",
    methods=["POST"],
)
@teacher_required
def unblock_resubmit_all(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        submissions = (
            db.query(Submission)
            .filter_by(
                lab_id=lab.id,
                is_current=True,
            )
            .all()
        )

        for submission in submissions:
            submission.resubmission_blocked = False
            submission.resubmission_message = (
                "Resubmission requests have been re-enabled by the teacher."
            )

        db.commit()

        return redirect(
            url_for(
                "lab_page",
                lab_id=lab.id,
            )
        )
  
# ============================================================
# Allow Resubmission For One Student
# ============================================================
@app.route(
    "/teacher/submission/<int:submission_id>/allow-resubmit",
    methods=["POST"],
)
@teacher_required
def allow_resubmission(submission_id):

    with SessionLocal() as db:

        submission = (
            db.query(Submission)
            .filter_by(
                id=submission_id,
            )
            .first()
        )

        if submission is None:
            return "Submission not found", 404

        if not submission.is_current:
            return (
                "Only the current submission can be modified.",
                400,
            )

        if submission.attempt_number >= MAX_SUBMISSION_ATTEMPTS:
            return (
                f"This student has already reached the maximum "
                f"of {MAX_SUBMISSION_ATTEMPTS} attempts.",
                400,
            )

        submission.resubmission_requested = False
        submission.resubmission_allowed = True
        submission.resubmission_message = (
            "Your resubmission request was approved by the teacher. "
            "You may submit one new attempt."
        )

        db.commit()

        return redirect(
            url_for(
                "lab_page",
                lab_id=submission.lab_id,
            )
        )

@app.route(
    "/teacher/lab/<int:lab_id>/allow-resubmit-all",
    methods=["POST"],
)
@teacher_required
def allow_resubmit_all(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        submissions = (
            db.query(Submission)
            .filter_by(
                lab_id=lab.id,
                is_current=True,
                resubmission_requested=True,
            )
            .all()
        )

        allowed_count = 0

        for submission in submissions:

            if submission.attempt_number >= MAX_SUBMISSION_ATTEMPTS:
                continue

            submission.resubmission_requested = False
            submission.resubmission_allowed = True
            submission.resubmission_message = (
                "Your resubmission request was approved by the teacher. "
                "You may submit one new attempt."
            )

            allowed_count += 1

        db.commit()

        app.logger.info(
            "Allowed resubmission for %s students in lab %s",
            allowed_count,
            lab.id,
        )

        return redirect(
            url_for(
                "lab_page",
                lab_id=lab.id,
            )
        )



#===========================================================
#teacher Reject 
#==========================================================
@app.route(
    "/teacher/submission/<int:submission_id>/reject-resubmit",
    methods=["POST"],
)
@teacher_required
def reject_resubmission(submission_id):

    with SessionLocal() as db:

        submission = (
            db.query(Submission)
            .filter_by(
                id=submission_id,
            )
            .first()
        )

        if submission is None:
            return "Submission not found", 404

        if not submission.is_current:
            return (
                "Only the current submission can be modified.",
                400,
            )

        if not submission.resubmission_requested:
            return (
                "There is no pending resubmission request.",
                400,
            )

        # ----------------------------------------------------
        # Record rejection
        # ----------------------------------------------------

        submission.resubmission_requested = False
        submission.resubmission_allowed = False
        submission.resubmission_rejections += 1

        # ----------------------------------------------------
        # Set message shown to student
        # ----------------------------------------------------

        if (
            submission.resubmission_rejections
            >= MAX_RESUBMISSION_REJECTIONS
        ):

            submission.resubmission_message = (
                f"Your resubmission request has been rejected "
                f"{MAX_RESUBMISSION_REJECTIONS} times. "
                "No further resubmission requests are allowed "
                "for this attempt."
            )

        else:

            remaining = (
                MAX_RESUBMISSION_REJECTIONS
                - submission.resubmission_rejections
            )

            submission.resubmission_message = (
                "Your resubmission request was rejected "
                "by the teacher. "
                f"You have {remaining} rejection request"
                f"{'s' if remaining != 1 else ''} remaining."
            )

        db.commit()

        app.logger.info(
            "Rejected resubmission request for submission %s. "
            "Rejections=%s",
            submission.id,
            submission.resubmission_rejections,
        )

        return redirect(
            url_for(
                "lab_page",
                lab_id=submission.lab_id,
            )
        )
# ============================================================
# Grade All Submissions For A Lab
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/grade-all",
    methods=["POST"],
)
@teacher_required
def grade_all_submissions(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return (
                "Lab not found",
                404,
            )

        submissions = (
            db.query(Submission)
            .options(
                joinedload(
                    Submission.student
                )
            )
            .filter_by(
                lab_id=lab.id,
                is_current=True,
            )
            .order_by(
                Submission.submitted_at.asc()
            )
            .all()
        )

        submission_data = [
            (
                submission.id,
                submission.student.github_username,
                submission.snapshot_path,
            )
            for submission in submissions
        ]

    grading_errors = []

    for (
        submission_id,
        student_username,
        snapshot_path,
    ) in submission_data:

        # ----------------------------------------------------
        # Snapshot is required for web grading
        # ----------------------------------------------------

        if not snapshot_path:

            message = (
                f"{student_username}: "
                "submission has no frozen repository snapshot"
            )

            grading_errors.append(message)

            app.logger.warning(
                "Skipping submission %s: no snapshot.",
                submission_id,
            )

            with SessionLocal() as db:

                submission = (
                    db.query(Submission)
                    .filter_by(
                        id=submission_id
                    )
                    .first()
                )

                if submission:

                    submission.status = (
                        "grading_error"
                    )

                    db.commit()

            continue

        # ----------------------------------------------------
        # Grade frozen snapshot
        # ----------------------------------------------------

        try:

            grade_submission(
                student_id=student_username,
                snapshot_path=snapshot_path,
                lab_id=lab.name,
                submission_id=submission_id,
            )

            # ------------------------------------------------
            # Mark as graded
            # ------------------------------------------------

            with SessionLocal() as db:

                submission = (
                    db.query(Submission)
                    .filter_by(
                        id=submission_id
                    )
                    .first()
                )

                if submission:

                    submission.status = "graded"

                    db.commit()

            app.logger.info(
                "Submission %s successfully graded.",
                submission_id,
            )

        except Exception as e:

            app.logger.exception(
                "Grading failed for submission %s",
                submission_id,
            )

            grading_errors.append(
                f"{student_username}: {e}"
            )

            with SessionLocal() as db:

                submission = (
                    db.query(Submission)
                    .filter_by(
                        id=submission_id
                    )
                    .first()
                )

                if submission:

                    submission.status = (
                        "grading_error"
                    )

                    db.commit()

    # --------------------------------------------------------
    # Log errors but continue processing all submissions
    # --------------------------------------------------------

    if grading_errors:

        app.logger.error(
            "Some submissions failed during bulk grading: %s",
            grading_errors,
        )

    return redirect(
        url_for(
            "lab_page",
            lab_id=lab_id,
        )
    )



# ============================================================
# Publish All Ready Results For A Lab
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/publish-all",
    methods=["POST"],
)
@teacher_required
def publish_all_ready_results(lab_id):
    published_count = 0
    already_published_count = 0
    not_ready_count = 0
    email_error_count = 0

    with SessionLocal() as db:
        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        submissions = (
            db.query(Submission)
            .options(
                joinedload(Submission.student),
                joinedload(Submission.lab),
                joinedload(Submission.grade),
            )
            .filter_by(
                lab_id=lab.id
            )
            .order_by(
                Submission.submitted_at.asc()
            )
            .all()
        )

        for submission in submissions:
            grade = submission.grade

            if submission.status == "published":
                already_published_count += 1
                continue

            if grade is None:
                not_ready_count += 1
                continue

            if grade.automatic_score is None:
                not_ready_count += 1
                continue

            if grade.teacher_score is None:
                not_ready_count += 1
                continue

            if submission.status != "graded":
                not_ready_count += 1
                continue

            final_score = (
                0.7 * grade.automatic_score
                + 0.3 * grade.teacher_score
            )

            grade.published_at = (
                datetime.now(timezone.utc)
            )

            submission.status = "published"

            db.commit()

            published_count += 1

            if submission.student.email:
                try:
                    send_grade_published_email(
                        student_email=(
                            submission.student.email
                        ),
                        student_username=(
                            submission.student.github_username
                        ),
                        lab_name=(
                            submission.lab.name
                        ),
                        score=final_score,
                        feedback=(
                            grade.feedback or ""
                        ),
                    )

                except Exception as e:
                    email_error_count += 1
                    app.logger.exception(
                        "Failed to send publication email "
                        "for submission %s: %s",
                        submission.id,
                        e,
                    )

    return redirect(
        url_for(
            "lab_page",
            lab_id=lab_id,
            published=published_count,
            already_published=(
                already_published_count
            ),
            not_ready=not_ready_count,
            email_errors=email_error_count,
        )
    )


# ============================================================
# Lab Launch Settings
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/launch",
    methods=["POST"],
)
@teacher_required
def update_lab_launch(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        action = request.form.get(
            "action",
            "",
        )

        if action == "launch":

            lab.launched = True

        elif action == "unlaunch":

            lab.launched = False

        else:

            return (
                "Invalid launch action.",
                400,
            )

        db.commit()

        return redirect(
            url_for(
                "lab_page",
                lab_id=lab.id,
            )
        )

# ============================================================
# Submission Window Settings
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/submission-settings",
    methods=["POST"],
)
@teacher_required
def update_submission_settings(lab_id):
    with SessionLocal() as db:
        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        action = request.form.get(
            "action",
            "",
        )

        deadline_text = request.form.get(
            "submission_deadline",
            "",
        ).strip()

        if deadline_text:
            try:
                naive_deadline = datetime.strptime(
                    deadline_text,
                    "%Y-%m-%dT%H:%M",
                )

                tunisian_time = naive_deadline.replace(
                    tzinfo=ZoneInfo("Africa/Tunis")
                )

                lab.submission_deadline = (
                    tunisian_time.astimezone(
                        timezone.utc
                    )
                )

            except ValueError:
                return (
                    "Invalid deadline format.",
                    400,
                )

        else:
            lab.submission_deadline = None

        now = datetime.now(timezone.utc)

        if action == "open":
            deadline = ensure_utc(
                lab.submission_deadline
            )

            if (
                deadline is not None
                and now >= deadline
            ):
                return (
                    "Cannot open submissions because "
                    "the deadline has already passed.",
                    400,
                )

            lab.submission_open = True

        elif action == "close":
            lab.submission_open = False

        elif action == "save_deadline":
            pass

        else:
            return (
                "Invalid submission settings action.",
                400,
            )

        db.commit()

        return redirect(
            url_for(
                "lab_page",
                lab_id=lab.id,
            )
        )


# ============================================================
# Grade One Notebook
# ============================================================

@app.route(
    "/teacher/submission/<int:submission_id>/grade-notebook",
    methods=["POST"],
)
@teacher_required
def grade_one_notebook(submission_id):
    notebook_filename = request.form.get(
        "notebook",
        "",
    ).strip()

    if not notebook_filename:
        return (
            "Notebook filename is required.",
            400,
        )

    with SessionLocal() as db:
        submission = (
            db.query(Submission)
            .options(
                joinedload(Submission.student),
                joinedload(Submission.lab),
            )
            .filter_by(id=submission_id)
            .first()
        )

        if submission is None:
            return (
                "Submission not found",
                404,
            )

        student_username = (
            submission.student.github_username
        )
        repo_url = submission.repo_url
        lab_name = submission.lab.name

    try:
        if not submission.snapshot_path:
            return (
                "This submission has no frozen repository snapshot. "
                "It cannot be graded.",
                400,
            )
        grade_submission(
            student_id=student_username,
            snapshot_path=submission.snapshot_path,
            lab_id=lab_name,
            submission_id=submission.id,
        )

    except Exception as e:
        app.logger.exception(
            "Notebook grading failed"
        )

        with SessionLocal() as db:
            submission = (
                db.query(Submission)
                .filter_by(id=submission_id)
                .first()
            )

            if submission:
                submission.status = "grading_error"
                db.commit()

        return (
            f"Grading failed: {e}",
            500,
        )

    return redirect(
        url_for(
            "teacher_submission_page",
            submission_id=submission_id,
        )
    )


# ============================================================
# Teacher Dashboard
# ============================================================

@app.route("/teacher")
@teacher_required
def teacher_dashboard():
    with SessionLocal() as db:
        submissions = (
            db.query(Submission)
            .options(
                joinedload(Submission.student),
                joinedload(Submission.lab),
                joinedload(Submission.grade),
            )
            .order_by(
                Submission.submitted_at.desc()
            )
            .all()
        )

        return render_template(
            "teacher_dashboard.html",
            submissions=submissions,
        )


# ============================================================
# GitHub Login
# ============================================================

@app.route("/login")
def login():
    redirect_uri = url_for(
        "github_callback",
        _external=True,
    )

    print("========================================")
    print("GITHUB REDIRECT URI:")
    print(redirect_uri)
    print("========================================")

    return github.authorize_redirect(
        redirect_uri
    )


# ============================================================
# GitHub OAuth Callback
# ============================================================

@app.route("/auth/github/callback")
def github_callback():
    token = github.authorize_access_token()

    user_response = github.get(
        "user",
        token=token,
    )

    github_user = user_response.json()

    github_id = str(
        github_user["id"]
    )

    github_username = (
        github_user["login"]
    )

    email = github_user.get("email")

    if not email:
        email_response = github.get(
            "user/emails",
            token=token,
        )

        emails = email_response.json()

        for item in emails:
            if (
                item.get("primary")
                and item.get("verified")
            ):
                email = item.get("email")
                break

    with SessionLocal() as db:
        student = (
            db.query(Student)
            .filter_by(
                github_id=github_id
            )
            .first()
        )

        if student is None:
            student = Student(
                github_username=github_username,
                github_id=github_id,
                email=email,
                role="student",
            )

            db.add(student)
            db.commit()
            db.refresh(student)

        else:
            student.github_username = (
                github_username
            )

            if email:
                student.email = email

            db.commit()

        session["student_id"] = student.id
        session["github_username"] = (
            student.github_username
        )
        session["role"] = student.role

    return redirect(
        url_for("home")
    )


# ============================================================
# Logout
# ============================================================

@app.route("/logout")
def logout():
    session.clear()

    return redirect(
        url_for("home")
    )


# ============================================================
# Development Server
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )

