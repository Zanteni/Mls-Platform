
import os
import re
import json
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
    Notification,
)
from .grading_db import (
    save_grading_result,
    finalize_lab_grade,
)
from urllib.parse import urlparse
import subprocess
import sys
from pathlib import Path

ALLOWED_GITHUB_HOSTS = {
    "github.com",
    "www.github.com",
}

GRADER_IMAGE = "mls-grader:1.0"
def validate_submission_repo_url(repo_url: str) -> bool:

    repo_url = repo_url.strip()

    parsed = urlparse(repo_url)

    if parsed.scheme != "https":
        return False

    if parsed.hostname not in ALLOWED_GITHUB_HOSTS:
        return False

    if parsed.username or parsed.password:
        return False

    if parsed.port is not None:
        return False

    path = parsed.path.strip("/")

    parts = path.split("/")

    if len(parts) != 2:
        return False

    owner, repo = parts

    if not owner or not repo:
        return False

    if ".." in path:
        return False

    return True

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
# Notification Helper
# ============================================================

def create_notification(
    db,
    student_id,
    notification_type,
    title,
    message,
    lab_id=None,
    submission_id=None,
):
    notification = Notification(
        student_id=student_id,
        lab_id=lab_id,
        submission_id=submission_id,
        notification_type=notification_type,
        title=title,
        message=message,
        read=False,
        read_at=None,
        created_at=datetime.now(timezone.utc),
    )

    db.add(notification)

    return notification

# ============================================================
# Create Immutable Repository Snapshot
# ============================================================

def create_repository_snapshot(
    repo_url,
    submission_id,
):
    """
    Clone a student's GitHub repository into an isolated
    submission directory and return:

        (snapshot_path, commit_sha)

    Security properties:
    - No shell execution
    - HTTPS-only Git protocol
    - No interactive credential prompts
    - No submodule recursion
    - Git hooks disabled for the cloned repository
    - Shallow clone
    - Hard timeout on Git operations
    - Per-submission filesystem isolation
    """

    # --------------------------------------------------------
    # Project root
    # --------------------------------------------------------

    root = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )


    # --------------------------------------------------------
    # Submission-specific paths
    # --------------------------------------------------------

    snapshot_root = (
        root
        / "data"
        / "submissions"
        / str(submission_id)
    )

    repo_path = (
        snapshot_root
        / "repo"
    )


    # --------------------------------------------------------
    # Defensive cleanup
    # --------------------------------------------------------

    if snapshot_root.exists():

        shutil.rmtree(
            snapshot_root
        )


    snapshot_root.mkdir(
        parents=True,
        exist_ok=True,
    )


    # --------------------------------------------------------
    # Restrict Git environment
    # --------------------------------------------------------

    env = os.environ.copy()

    # Never allow Git to prompt for username/password.
    env["GIT_TERMINAL_PROMPT"] = "0"

    # Only allow HTTPS for automated clone/fetch operations.
    #
    # This is a whitelist, not just a blacklist.
    env["GIT_ALLOW_PROTOCOL"] = "https"

    # Do not allow protocols configured as "user" to be
    # activated by automated Git operations.
    env["GIT_PROTOCOL_FROM_USER"] = "0"

    # Ignore system Git configuration for this subprocess.
    env["GIT_CONFIG_NOSYSTEM"] = "1"

    # Prevent a user's global Git configuration from changing
    # URL rewriting, helpers, etc.
    env["GIT_CONFIG_GLOBAL"] = os.devnull


    # --------------------------------------------------------
    # Common Git security configuration
    # --------------------------------------------------------

    git_security_config = [
        "-c",
        "protocol.ext.allow=never",

        "-c",
        "protocol.file.allow=never",

        "-c",
        "protocol.ssh.allow=never",

        "-c",
        "protocol.git.allow=never",

        "-c",
        "core.hooksPath=NUL",
    ]


    try:

        # ====================================================
        # CLONE
        # ====================================================

        clone_command = [
            "git",
            *git_security_config,

            "clone",

            "--depth",
            "1",

            "--no-tags",

            "--no-recurse-submodules",

            repo_url,

            str(repo_path),
        ]


        subprocess.run(
            clone_command,

            check=True,

            capture_output=True,

            text=True,

            timeout=120,

            env=env,
        )


        # ====================================================
        # VERIFY REPOSITORY EXISTS
        # ====================================================

        if not repo_path.exists():

            raise RuntimeError(
                "Git clone completed but "
                "the repository directory was not created."
            )


        # ====================================================
        # GET COMMIT SHA
        # ====================================================

        commit_command = [
            "git",
            *git_security_config,

            "-C",
            str(repo_path),

            "rev-parse",
            "HEAD",
        ]


        result = subprocess.run(
            commit_command,

            check=True,

            capture_output=True,

            text=True,

            timeout=30,

            env=env,
        )


        commit_sha = (
            result.stdout.strip()
        )


        # ----------------------------------------------------
        # Validate commit SHA
        # ----------------------------------------------------

        if not re.fullmatch(
            r"[0-9a-fA-F]{40,64}",
            commit_sha,
        ):

            raise RuntimeError(
                "Git returned an invalid commit SHA."
            )


        # ====================================================
        # RETURN SNAPSHOT
        # ====================================================

        return (
            str(repo_path),
            commit_sha,
        )


    except subprocess.TimeoutExpired as e:

        app.logger.warning(
            "Git operation timed out for "
            "submission %s",
            submission_id,
        )

        if snapshot_root.exists():

            shutil.rmtree(
                snapshot_root
            )

        raise RuntimeError(
            "Repository snapshot timed out."
        ) from e


    except subprocess.CalledProcessError as e:

        stderr = (
            e.stderr
            or ""
        ).strip()

        # Don't expose the complete Git command or potentially
        # sensitive subprocess information to students.
        app.logger.warning(
            "Git operation failed for submission %s: %s",
            submission_id,
            stderr[-2000:],
        )

        if snapshot_root.exists():

            shutil.rmtree(
                snapshot_root
            )

        raise RuntimeError(
            "Could not create repository snapshot."
        ) from e


    except Exception:

        if snapshot_root.exists():

            shutil.rmtree(
                snapshot_root
            )

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
@app.context_processor
def inject_notification_count():

    unread_notification_count = 0

    if session.get("student_id"):

        with SessionLocal() as db:

            unread_notification_count = (
                db.query(Notification)
                .filter(
                    Notification.student_id
                    == session["student_id"],
                    Notification.read == False,
                )
                .count()
            )

    return {
        "unread_notification_count":
            unread_notification_count
    }
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
            .filter_by(
                archived=False,
                visible=True,
            )
            .order_by(
                Lab.display_order.asc(),
                Lab.id.asc(),
            )
            .all()
        )
        return render_template(
            "home.html",
            labs=labs,
        )

# ============================================================
# Lab Details
# ============================================================

@app.route(
    "/lab/<int:lab_id>/details"
)
@login_required
def lab_details(lab_id):

    with SessionLocal() as db:

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
        # Students cannot access archived/hidden labs
        # ----------------------------------------------------

        if session.get("role") != "teacher":

            if lab.archived or not lab.visible:
                return (
                    "This laboratory is not available.",
                    404,
                )

        return render_template(
            "labs/detail.html",
            lab=lab,
        )
# ============================================================
# Edit Lab
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/edit",
    methods=["GET", "POST"],
)
@teacher_required
def edit_lab(lab_id):

    with SessionLocal() as db:

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

        if request.method == "POST":

            # ------------------------------------------------
            # Basic information
            # ------------------------------------------------

            name = request.form.get(
                "name",
                "",
            ).strip()

            description = request.form.get(
                "description",
                "",
            ).strip()

            github_url = request.form.get(
                "github_url",
                "",
            ).strip()

            category = request.form.get(
                "category",
                "",
            ).strip()

            # ------------------------------------------------
            # Organization
            # ------------------------------------------------

            display_order = request.form.get(
                "display_order",
                0,
                type=int,
            )

            # ------------------------------------------------
            # Learning content
            # ------------------------------------------------

            solution_url = request.form.get(
                "solution_url",
                "",
            ).strip()

            video_url = request.form.get(
                "video_url",
                "",
            ).strip()

            teacher_notes = request.form.get(
                "teacher_notes",
                "",
            ).strip()

            # ------------------------------------------------
            # Validation
            # ------------------------------------------------

            if not name:

                flash(
                    "Lab name is required.",
                    "warning",
                )

                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab.id,
                    )
                )

            if not github_url:

                flash(
                    "GitHub assignment URL is required.",
                    "warning",
                )

                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab.id,
                    )
                )

            # ------------------------------------------------
            # Check duplicate name
            # ------------------------------------------------

            duplicate = (
                db.query(Lab)
                .filter(
                    Lab.name == name,
                    Lab.id != lab.id,
                )
                .first()
            )

            if duplicate:

                flash(
                    "Another lab already uses this name.",
                    "warning",
                )

                return redirect(
                    url_for(
                        "edit_lab",
                        lab_id=lab.id,
                    )
                )

            # ------------------------------------------------
            # Update Lab
            # ------------------------------------------------

            lab.name = name
            lab.description = (
                description or None
            )
            lab.github_url = github_url
            lab.category = (
                category or None
            )

            lab.display_order = (
                display_order
            )

            lab.solution_url = (
                solution_url or None
            )

            lab.video_url = (
                video_url or None
            )

            lab.teacher_notes = (
                teacher_notes or None
            )

            db.commit()

            flash(
                "Lab updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "lab_details",
                    lab_id=lab.id,
                )
            )

        return render_template(
            "labs/edit.html",
            lab=lab,
        )

# ============================================================
# Lab page
# ============================================================

@app.route(
    "/lab/<int:lab_id>"
)
@login_required
def lab_page(lab_id):

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
        # Current time
        # ----------------------------------------------------

        now = datetime.now(
            timezone.utc
        )

        # ----------------------------------------------------
        # Normalize deadline
        # ----------------------------------------------------

        if lab.submission_deadline is not None:

            lab.submission_deadline = (
                ensure_utc(
                    lab.submission_deadline
                )
            )

        # ----------------------------------------------------
        # Load submissions
        # ----------------------------------------------------

        query = (
            db.query(Submission)
            .options(
                joinedload(
                    Submission.student
                ),
                joinedload(
                    Submission.grade
                ),
            )
            .filter_by(
                lab_id=lab.id
            )
        )

        # ----------------------------------------------------
        # Students only see their own submissions
        # ----------------------------------------------------

        if session.get("role") != "teacher":

            query = query.filter(
                Submission.student_id
                == session["student_id"]
            )

        # ----------------------------------------------------
        # Order submissions
        # ----------------------------------------------------

        submissions = (
            query
            .order_by(
                Submission.submitted_at.desc()
            )
            .all()
        )

        # ----------------------------------------------------
        # Select template
        # ----------------------------------------------------

        if session.get("role") == "teacher":

            template = (
                "labs/teacher.html"
            )

        else:

            template = (
                "labs/student.html"
            )

        # ----------------------------------------------------
        # Render
        # ----------------------------------------------------

        return render_template(
            template,
            lab=lab,
            submissions=submissions,
            now=now,
        )


# ============================================================
# Submit Lab
# ============================================================

@app.route(
    "/lab/<int:lab_id>/submit",
    methods=["POST"],
)
@login_required
def submit_lab(lab_id):

    # --------------------------------------------------------
    # Get repository URL
    # --------------------------------------------------------

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


    if not validate_submission_repo_url(
        repo_url
    ):

        flash(
            "Please submit a valid HTTPS GitHub repository URL.",
            "warning",
        )

        return redirect(
            url_for(
                "lab_page",
                lab_id=lab_id,
            )
        )


    with SessionLocal() as db:

        # ====================================================
        # LOAD LAB
        # ====================================================

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


        # ====================================================
        # LAB MUST BE LAUNCHED
        # ====================================================

        if not lab.launched:

            return (
                "This laboratory has not been launched yet.",
                403,
            )


        # ====================================================
        # GET STUDENT
        # ====================================================

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


        # ====================================================
        # FIND CURRENT SUBMISSION
        # ====================================================

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
        # Existing current submission
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
                    f"{MAX_SUBMISSION_ATTEMPTS} attempts "
                    "for this lab.",
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

        # Teacher-approved resubmissions are allowed even
        # when the normal submission window is closed.

        if not is_resubmission:

            now = datetime.now(
                timezone.utc
            )

            deadline = ensure_utc(
                lab.submission_deadline
            )


            # -----------------------------------------------
            # Manual close
            # -----------------------------------------------

            if not lab.submission_open:

                return (
                    "Submissions are currently closed "
                    "for this lab.",
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
                    "The submission deadline for this lab "
                    "has passed.",
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

        db.add(
            submission
        )


        # ----------------------------------------------------
        # Get submission ID before snapshot creation
        # ----------------------------------------------------

        db.flush()


        # ====================================================
        # CREATE IMMUTABLE REPOSITORY SNAPSHOT
        # ====================================================

        try:

            snapshot_path, commit_sha = (
                create_repository_snapshot(
                    repo_url=repo_url,
                    submission_id=submission.id,
                )
            )

        except Exception as e:

            # ------------------------------------------------
            # Roll back database changes.
            # ------------------------------------------------
            #
            # For a resubmission, the previous submission
            # remains current.
            #

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
        # PREVIOUS CURRENT SUBMISSION BECOMES HISTORICAL
        # ====================================================

        if current_submission is not None:

            current_submission.is_current = False

            current_submission.resubmission_allowed = False

            current_submission.resubmission_requested = False

            current_submission.resubmission_message = None


        # ====================================================
        # SAVE SNAPSHOT INFORMATION
        # ====================================================

        submission.snapshot_path = (
            snapshot_path
        )

        submission.commit_sha = (
            commit_sha
        )


        # ====================================================
        # SAVE DATABASE CHANGES
        # ====================================================

        db.commit()

        db.refresh(
            submission
        )


        # ====================================================
        # LOG SUCCESS
        # ====================================================

        app.logger.info(
            "Submission %s created successfully. "
            "Student=%s Lab=%s Attempt=%s "
            "Commit=%s Snapshot=%s",
            submission.id,
            student.github_username,
            lab.name,
            submission.attempt_number,
            submission.commit_sha,
            submission.snapshot_path,
        )


        # ====================================================
        # REDIRECT
        # ====================================================

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
# ============================================================
# Reject All Pending Resubmission Requests
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/reject-resubmit-all",
    methods=["POST"],
)
@teacher_required
def reject_resubmit_all(lab_id):

    with SessionLocal() as db:

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

            # ------------------------------------------------
            # Notification
            # ------------------------------------------------

            create_notification(
                db=db,
                student_id=submission.student_id,
                notification_type="resubmission",
                title="Resubmission Request Rejected",
                message=submission.resubmission_message,
                lab_id=submission.lab_id,
                submission_id=submission.id,
            )

            rejected_count += 1

        db.commit()

        app.logger.info(
            "Rejected %s resubmission requests in lab %s",
            rejected_count,
            lab.id,
        )

        flash(
            f"{rejected_count} resubmission request(s) rejected.",
            "warning",
        )

        return redirect(
            url_for(
                "teacher_lab_submissions",
                lab_id=lab.id,
            )
        )
# ============================================================
# Teacher Grading Page
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
                joinedload(
                    Submission.student
                ),
                joinedload(
                    Submission.lab
                ),
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

        # ----------------------------------------------------
        # Create Grade object if necessary
        # ----------------------------------------------------

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

        # ====================================================
        # POST
        # ====================================================

        if request.method == "POST":

            teacher_score = request.form.get(
                "teacher_score",
                type=float,
            )

            feedback = request.form.get(
                "feedback",
                "",
            ).strip()

            action = request.form.get(
                "action"
            )

            # ------------------------------------------------
            # Validate teacher score
            # ------------------------------------------------

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

            # =================================================
            # SAVE DRAFT
            # =================================================

            if action == "save":

                grade.teacher_score = (
                    teacher_score
                )

                grade.feedback = (
                    feedback
                )

                db.commit()

                return redirect(
                    url_for(
                        "teacher_submission_page",
                        submission_id=submission.id,
                    )
                )

            # =================================================
            # PUBLISH
            # =================================================

            if action == "publish":

                # --------------------------------------------
                # Submission must be graded
                # --------------------------------------------

                if submission.status not in (
                    "graded",
                    "published",
                ):

                    return (
                        "This submission must be graded before "
                        "it can be published.",
                        400,
                    )

                # --------------------------------------------
                # Automatic grade required
                # --------------------------------------------

                if (
                    grade.automatic_score
                    is None
                ):

                    return (
                        "Automatic grading must be completed "
                        "before publishing.",
                        400,
                    )

                # --------------------------------------------
                # Calculate final score
                # --------------------------------------------

                final_score = (
                    0.7
                    * grade.automatic_score
                    +
                    0.3
                    * teacher_score
                )

                # --------------------------------------------
                # Update grade
                # --------------------------------------------

                grade.teacher_score = (
                    teacher_score
                )

                grade.feedback = (
                    feedback
                )

                # --------------------------------------------
                # First publication?
                # --------------------------------------------

                first_publication = (
                    grade.published_at is None
                )

                if first_publication:

                    grade.published_at = (
                        datetime.now(
                            timezone.utc
                        )
                    )

                # --------------------------------------------
                # Update submission state
                # --------------------------------------------

                submission.status = (
                    "published"
                )

                # --------------------------------------------
                # Create notification ONLY on
                # first publication
                # --------------------------------------------

                if first_publication:

                    notification_message = (
                        f"Your final grade for "
                        f"{submission.lab.name} "
                        f"has been published. "
                        f"Your final score is "
                        f"{final_score:.2f}/100."
                    )

                    create_notification(
                        db=db,
                        student_id=(
                            submission.student_id
                        ),
                        notification_type="grade",
                        title="Grade Published",
                        message=notification_message,
                        lab_id=(
                            submission.lab_id
                        ),
                        submission_id=(
                            submission.id
                        ),
                    )

                # --------------------------------------------
                # Save grade + publication +
                # notification together
                # --------------------------------------------

                db.commit()

                # --------------------------------------------
                # Email notification
                # --------------------------------------------

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

                # --------------------------------------------
                # Clean terminal output
                # --------------------------------------------

                for notebook in grade.notebooks:

                    for check in notebook.checks:

                        check.message = (
                            clean_terminal_text(
                                check.message
                            )
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

        # ====================================================
        # GET
        # ====================================================

        for notebook in grade.notebooks:

            for check in notebook.checks:

                check.message = (
                    clean_terminal_text(
                        check.message
                    )
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

    # --------------------------------------------------------
    # Load submission information
    # --------------------------------------------------------

    with SessionLocal() as db:

        submission = (
            db.query(Submission)
            .options(
                joinedload(
                    Submission.student
                ),
                joinedload(
                    Submission.lab
                ),
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

        if not submission.snapshot_path:

            return (
                "This submission has no frozen repository snapshot. "
                "It cannot be graded.",
                400,
            )

        student_username = (
            submission.student.github_username
        )

        snapshot_path = (
            submission.snapshot_path
        )

        lab_name = (
            submission.lab.name
        )

        lab_id = lab_name

    # --------------------------------------------------------
    # Verify snapshot exists on the host
    # --------------------------------------------------------

    snapshot = Path(
        snapshot_path
    ).resolve()

    if not snapshot.exists():

        app.logger.error(
            "Snapshot does not exist for submission %s: %s",
            submission_id,
            snapshot,
        )

        return (
            "The frozen repository snapshot could not be found.",
            500,
        )

    # --------------------------------------------------------
    # Docker command
    # --------------------------------------------------------

    command = [
        "docker",
        "run",
        "--rm",

        # -----------------------------------------------
        # Network isolation
        # -----------------------------------------------

        "--network",
        "none",

        # -----------------------------------------------
        # Read-only container filesystem
        # -----------------------------------------------

        "--read-only",

        # -----------------------------------------------
        # No Linux capabilities
        # -----------------------------------------------

        "--cap-drop",
        "ALL",

        # -----------------------------------------------
        # Prevent privilege escalation
        # -----------------------------------------------

        "--security-opt",
        "no-new-privileges",

        # -----------------------------------------------
        # Resource limits
        # -----------------------------------------------

        "--memory",
        "2g",

        "--cpus",
        "2",

        "--pids-limit",
        "128",

        # -----------------------------------------------
        # Writable temporary filesystem only
        # -----------------------------------------------

        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=512m",

        # -----------------------------------------------
        # Student snapshot ONLY
        #
        # Read-only mount.
        # -----------------------------------------------

        "--mount",
        (
            "type=bind,"
            f"source={snapshot},"
            "target=/grader/submission,"
            "readonly"
        ),

        # -----------------------------------------------
        # Image
        # -----------------------------------------------

        GRADER_IMAGE,

        # -----------------------------------------------
        # Worker arguments
        # -----------------------------------------------

        "--student-id",
        student_username,

        "--lab-id",
        lab_id,

        "--snapshot-path",
        "/grader/submission",

        "--submission-id",
        str(submission_id),
    ]

    app.logger.info(
        "Starting Docker grading container "
        "for submission %s",
        submission_id,
    )

    # --------------------------------------------------------
    # Run Docker
    # --------------------------------------------------------

    try:

        result = subprocess.run(
            command,
            cwd=str(
                Path(__file__)
                .resolve()
                .parent
                .parent
            ),
            capture_output=True,
            text=True,
            timeout=15 * 60,
            check=False,
        )

    except subprocess.TimeoutExpired:

        app.logger.error(
            "Docker grading timed out "
            "for submission %s",
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

        return (
            "Automatic grading timed out.",
            500,
        )

    except Exception as e:

        app.logger.exception(
            "Could not start Docker grading "
            "for submission %s",
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

        return (
            "Could not start the grading container.",
            500,
        )

    # --------------------------------------------------------
    # Log worker output
    # --------------------------------------------------------

    if result.stdout:

        app.logger.info(
            "Docker grader stdout for submission %s:\n%s",
            submission_id,
            result.stdout[-10000:],
        )

    if result.stderr:

        app.logger.warning(
            "Docker grader stderr for submission %s:\n%s",
            submission_id,
            result.stderr[-10000:],
        )

    # --------------------------------------------------------
    # Docker process failed
    # --------------------------------------------------------

    if result.returncode != 0:

        app.logger.error(
            "Docker grader failed for submission %s "
            "with return code %s",
            submission_id,
            result.returncode,
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

        return (
            "Automatic grading failed.",
            500,
        )

    # ========================================================
    # Parse grading JSON
    # ========================================================

    marker = "GRADING_RESULT_JSON:"

    result_payload = None

    for line in reversed(
        result.stdout.splitlines()
    ):

        if not line.startswith(marker):
            continue

        json_payload = (
            line[len(marker):].strip()
        )

        try:

            result_payload = json.loads(
                json_payload
            )

        except json.JSONDecodeError:

            app.logger.exception(
                "Invalid grading JSON for submission %s",
                submission_id,
            )

        break

    # --------------------------------------------------------
    # No JSON result
    # --------------------------------------------------------

    if result_payload is None:

        app.logger.error(
            "No valid grading result returned "
            "for submission %s",
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

        return (
            "The grading container returned no valid result.",
            500,
        )

    # --------------------------------------------------------
    # Worker reported failure
    # --------------------------------------------------------

    if not result_payload.get(
        "success",
        False,
    ):

        app.logger.error(
            "Grading worker reported failure "
            "for submission %s",
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

        return (
            "Automatic grading failed.",
            500,
        )

    # ========================================================
    # Save grading results into application database
    # ========================================================

    grading_results = (
        result_payload.get(
            "results",
            []
        )
    )

    if not grading_results:

        app.logger.error(
            "No notebook results returned "
            "for submission %s",
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

        return (
            "Grading produced no notebook results.",
            500,
        )

    try:

        # ----------------------------------------------------
        # Save notebook-level results
        # ----------------------------------------------------

        for grading_result in grading_results:

            save_grading_result(
                grading_result,
                submission_id=submission_id,
            )

        # ----------------------------------------------------
        # Calculate overall automatic grade
        # ----------------------------------------------------

        finalize_lab_grade(
            student_username,
            lab_name,
            submission_id=submission_id,
        )

    except Exception:

        app.logger.exception(
            "Failed to save grading results "
            "for submission %s",
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

        return (
            "Grading completed, but the results "
            "could not be saved.",
            500,
        )

    # ========================================================
    # Mark submission as graded
    # ========================================================

    with SessionLocal() as db:

        submission = (
            db.query(Submission)
            .filter_by(
                id=submission_id
            )
            .first()
        )

        if submission is None:

            return (
                "Submission not found after grading.",
                404,
            )

        submission.status = (
            "graded"
        )

        db.commit()

        app.logger.info(
            "Submission %s successfully graded "
            "inside Docker sandbox.",
            submission_id,
        )

    # ========================================================
    # Return to teacher page
    # ========================================================

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
        create_notification(
            db=db,
            student_id=submission.student_id,
            notification_type="resubmission",
            title="Resubmission Requests Blocked",
            message=(
                "The teacher has blocked resubmission requests "
                "for this submission."
            ),
            lab_id=submission.lab_id,
            submission_id=submission.id,
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
# ============================================================
# Block Resubmission Requests For All Current Students
# ============================================================

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

        blocked_count = 0

        for submission in submissions:

            submission.resubmission_blocked = True
            submission.resubmission_requested = False
            submission.resubmission_allowed = False

            submission.resubmission_message = (
                "Resubmission requests have been blocked "
                "by the teacher."
            )

            create_notification(
                db=db,
                student_id=submission.student_id,
                notification_type="resubmission",
                title="Resubmission Requests Blocked",
                message=submission.resubmission_message,
                lab_id=submission.lab_id,
                submission_id=submission.id,
            )

            blocked_count += 1

        db.commit()

        flash(
            f"{blocked_count} student(s) now have resubmission "
            "requests blocked.",
            "warning",
        )

        return redirect(
            url_for(
                "teacher_lab_submissions",
                lab_id=lab.id,
            )
        )
#unblock alll
# ============================================================
# Unblock Resubmission Requests For All Current Students
# ============================================================

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
                resubmission_blocked=True,
            )
            .all()
        )

        unblocked_count = 0

        for submission in submissions:

            submission.resubmission_blocked = False

            submission.resubmission_message = (
                "Resubmission requests have been re-enabled "
                "by the teacher."
            )

            create_notification(
                db=db,
                student_id=submission.student_id,
                notification_type="resubmission",
                title="Resubmission Requests Re-enabled",
                message=submission.resubmission_message,
                lab_id=submission.lab_id,
                submission_id=submission.id,
            )

            unblocked_count += 1

        db.commit()

        flash(
            f"{unblocked_count} student(s) can request "
            "resubmission again.",
            "success",
        )

        return redirect(
            url_for(
                "teacher_lab_submissions",
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
            return (
                "Submission not found",
                404,
            )

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

        if not submission.resubmission_requested:
            return (
                "There is no pending resubmission request.",
                400,
            )

        # ----------------------------------------------------
        # Approve resubmission
        # ----------------------------------------------------

        submission.resubmission_requested = False
        submission.resubmission_allowed = True

        submission.resubmission_message = (
            "Your resubmission request was approved by the teacher. "
            "You may submit one new attempt."
        )

        # ----------------------------------------------------
        # Create notification
        # ----------------------------------------------------

        create_notification(
            db=db,
            student_id=submission.student_id,
            notification_type="resubmission",
            title="Resubmission Request Approved",
            message=submission.resubmission_message,
            lab_id=submission.lab_id,
            submission_id=submission.id,
        )

        # ----------------------------------------------------
        # Save both changes together
        # ----------------------------------------------------

        db.commit()

        app.logger.info(
            "Approved resubmission request for submission %s",
            submission.id,
        )

        return redirect(
            url_for(
                "lab_page",
                lab_id=submission.lab_id,
            )
        )
    
# ============================================================
# Allow Resubmission For All Eligible Students
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/allow-resubmit-all",
    methods=["POST"],
)
@teacher_required
def allow_resubmit_all(lab_id):

    with SessionLocal() as db:

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

            if (
                submission.attempt_number
                >= MAX_SUBMISSION_ATTEMPTS
            ):
                continue

            submission.resubmission_requested = False
            submission.resubmission_allowed = True

            submission.resubmission_message = (
                "Your resubmission request was approved by the teacher. "
                "You may submit one new attempt."
            )

            # ------------------------------------------------
            # Notification
            # ------------------------------------------------

            create_notification(
                db=db,
                student_id=submission.student_id,
                notification_type="resubmission",
                title="Resubmission Request Approved",
                message=(
                    "Your resubmission request was approved by the teacher. "
                    "You may submit one new attempt."
                ),
                lab_id=submission.lab_id,
                submission_id=submission.id,
            )

            allowed_count += 1

        db.commit()

        app.logger.info(
            "Allowed resubmission for %s students in lab %s",
            allowed_count,
            lab.id,
        )

        flash(
            f"{allowed_count} resubmission request(s) approved.",
            "success",
        )

        return redirect(
            url_for(
                "teacher_lab_submissions",
                lab_id=lab.id,
            )
        )


# ============================================================
# Teacher Reject Resubmission
# ============================================================
@app.route(
    "/teacher/submission/<int:submission_id>/reject-resubmit",
    methods=["POST"],
)
@teacher_required
def reject_resubmission(submission_id):

    print(
        "================ REJECT ROUTE ================="
    )

    print(
        "Received submission_id:",
        submission_id,
    )

    with SessionLocal() as db:

        submission = (
            db.query(Submission)
            .filter_by(
                id=submission_id,
            )
            .first()
        )

        print(
            "Submission found:",
            submission is not None,
        )

        if submission is None:
            return "Submission not found", 404

        print(
            "is_current:",
            submission.is_current,
        )

        print(
            "resubmission_requested:",
            submission.resubmission_requested,
        )

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

        print(
            "Creating notification for student:",
            submission.student_id,
        )

        notification = create_notification(
            db=db,
            student_id=submission.student_id,
            notification_type="resubmission",
            title="Resubmission Request Rejected",
            message=submission.resubmission_message,
            lab_id=submission.lab_id,
            submission_id=submission.id,
        )

        print(
            "Notification object:",
            notification,
        )

        db.commit()

        print(
            "COMMITTED REJECTION + NOTIFICATION"
        )

        print(
            "================================================"
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

    # --------------------------------------------------------
    # Load lab and current submissions
    # --------------------------------------------------------

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
                joinedload(Submission.student)
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

    # --------------------------------------------------------
    # Grade every submission independently
    # --------------------------------------------------------

    grading_errors = []

    for (
        submission_id,
        student_username,
        snapshot_path,
    ) in submission_data:

        # ----------------------------------------------------
        # Snapshot is required
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
        # Grade this submission
        # ----------------------------------------------------

        try:

            grading_results = grade_submission(
                student_id=student_username,
                snapshot_path=snapshot_path,
                lab_id=lab.name,
                submission_id=submission_id,
            )

            # ------------------------------------------------
            # Verify grading returned results
            # ------------------------------------------------

            if not grading_results:

                raise ValueError(
                    "Grading produced no notebook results."
                )

            # ------------------------------------------------
            # Save notebook-level results
            # ------------------------------------------------

            for grading_result in grading_results:

                save_grading_result(
                    grading_result,
                    submission_id=submission_id,
                )

            # ------------------------------------------------
            # Calculate overall grade
            # ------------------------------------------------

            finalize_lab_grade(
                student_username,
                lab.name,
                submission_id=submission_id,
            )

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

            # -----------------------------------------------
            # IMPORTANT:
            #
            # Continue with the next student.
            # -----------------------------------------------

            continue

    # --------------------------------------------------------
    # Log errors but continue processing all submissions
    # --------------------------------------------------------

    if grading_errors:

        app.logger.error(
            "Some submissions failed during bulk grading: %s",
            grading_errors,
        )

    else:

        app.logger.info(
            "All submissions for lab %s "
            "were graded successfully.",
            lab_id,
        )

    # --------------------------------------------------------
    # Return to lab page
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Load submission information
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Snapshot is required
    # --------------------------------------------------------

    if not snapshot_path:
        return (
            "This submission has no frozen repository snapshot. "
            "It cannot be graded.",
            400,
        )

    # --------------------------------------------------------
    # Grade ONLY the requested notebook
    # --------------------------------------------------------

    try:

        grading_results = grade_submission(
            student_id=student_username,
            snapshot_path=snapshot_path,
            lab_id=lab_name,
            notebook_filename=notebook_filename,
            submission_id=submission_id,
        )

        # ----------------------------------------------------
        # Verify that grading returned a result
        # ----------------------------------------------------

        if not grading_results:

            raise ValueError(
                "Notebook grading produced no result."
            )

        # ----------------------------------------------------
        # Save notebook result(s)
        # ----------------------------------------------------

        for grading_result in grading_results:

            save_grading_result(
                grading_result,
                submission_id=submission_id,
            )

        # ----------------------------------------------------
        # Recalculate overall grade
        #
        # IMPORTANT:
        #
        # If only one notebook was graded, the existing results
        # for the other notebooks remain in the database.
        #
        # finalize_lab_grade() therefore calculates the grade
        # from all notebook results currently belonging to
        # this submission.
        # ----------------------------------------------------

        finalize_lab_grade(
            student_username,
            lab_name,
            submission_id=submission_id,
        )

    except Exception as e:

        app.logger.exception(
            "Notebook grading failed for submission %s",
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

        return (
            f"Grading failed: {e}",
            500,
        )

    # --------------------------------------------------------
    # Final verification
    # --------------------------------------------------------

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
                "graded"
            )

            db.commit()

    app.logger.info(
        "Notebook %s successfully graded "
        "for submission %s.",
        notebook_filename,
        submission_id,
    )

    # --------------------------------------------------------
    # Return to teacher page
    # --------------------------------------------------------

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

        labs = (
            db.query(Lab)
            .filter(
                Lab.archived.is_(False)
            )
            .order_by(
                Lab.display_order.asc(),
                Lab.id.asc(),
            )
            .all()
        )

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
            labs=labs,
            submissions=submissions,
        )
# ============================================================
# Archived Labs
# ============================================================

@app.route("/teacher/archived-labs")
@teacher_required
def teacher_archived_labs():

    with SessionLocal() as db:

        archived_labs = (
            db.query(Lab)
            .filter(
                Lab.archived.is_(True)
            )
            .order_by(
                Lab.updated_at.desc(),
                Lab.id.desc(),
            )
            .all()
        )

        return render_template(
            "teacher_archived_labs.html",
            archived_labs=archived_labs,
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
# Create New Lab
# ============================================================

@app.route(
    "/teacher/labs/new",
    methods=["GET", "POST"],
)
@teacher_required
def create_lab():

    with SessionLocal() as db:

        if request.method == "POST":

            name = request.form.get(
                "name",
                "",
            ).strip()

            description = request.form.get(
                "description",
                "",
            ).strip()

            github_url = request.form.get(
                "github_url",
                "",
            ).strip()

            category = request.form.get(
                "category",
                "",
            ).strip()

            display_order = request.form.get(
                "display_order",
                0,
                type=int,
            )

            solution_url = request.form.get(
                "solution_url",
                "",
            ).strip()

            video_url = request.form.get(
                "video_url",
                "",
            ).strip()

            teacher_notes = request.form.get(
                "teacher_notes",
                "",
            ).strip()

            if not name:

                flash(
                    "Lab name is required.",
                    "warning",
                )

                return redirect(
                    url_for("create_lab")
                )

            if not github_url:

                flash(
                    "GitHub repository URL is required.",
                    "warning",
                )

                return redirect(
                    url_for("create_lab")
                )

            existing_lab = (
                db.query(Lab)
                .filter_by(
                    name=name
                )
                .first()
            )

            if existing_lab:

                flash(
                    "A lab with this name already exists.",
                    "warning",
                )

                return redirect(
                    url_for("create_lab")
                )

            # ------------------------------------------------
            # Generate unique slug
            # ------------------------------------------------

            slug_base = re.sub(
                r"[^a-z0-9]+",
                "-",
                name.lower(),
            ).strip("-")

            if not slug_base:
                slug_base = "lab"

            slug = slug_base
            counter = 2

            while (
                db.query(Lab)
                .filter_by(slug=slug)
                .first()
                is not None
            ):

                slug = (
                    f"{slug_base}-{counter}"
                )

                counter += 1

            # ------------------------------------------------
            # Create lab
            # ------------------------------------------------

            lab = Lab(
                name=name,
                slug=slug,
                description=description or None,
                github_url=github_url,
                display_order=display_order,
                category=category or None,
                archived=False,
                visible=True,
                launched=False,
                submission_open=False,
                submission_deadline=None,
                solution_url=solution_url or None,
                video_url=video_url or None,
                teacher_notes=teacher_notes or None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            db.add(lab)

            db.commit()

            db.refresh(lab)

            flash(
                f'Lab "{lab.name}" created successfully.',
                "success",
            )

            return redirect(
                url_for(
                    "lab_details",
                    lab_id=lab.id,
                )
            )

        return render_template(
            "labs/new.html"
        )

# ============================================================
# Archive Lab
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/archive",
    methods=["POST"],
)
@teacher_required
def archive_lab(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        lab.archived = True

        # An archived lab should not remain publicly accessible.
        lab.visible = False

        # Stop new submissions.
        lab.submission_open = False

        db.commit()

        flash(
            f'Lab "{lab.name}" has been archived.',
            "success",
        )

        return redirect(
            url_for("teacher_dashboard")
        )


# ============================================================
# Restore Lab
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/restore",
    methods=["POST"],
)
@teacher_required
def restore_lab(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        lab.archived = False

        # Restoring does not automatically launch the lab
        # or open submissions.
        lab.visible = True
        lab.launched = False
        lab.submission_open = False

        db.commit()

        flash(
            f'Lab "{lab.name}" has been restored.',
            "success",
        )

        return redirect(
            url_for("teacher_dashboard")
        )


# ============================================================
# Hide Lab
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/hide",
    methods=["POST"],
)
@teacher_required
def hide_lab(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        lab.visible = False

        db.commit()

        flash(
            f'Lab "{lab.name}" is now hidden from students.',
            "success",
        )

        return redirect(
            url_for("teacher_dashboard")
        )


# ============================================================
# Show Lab
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/show",
    methods=["POST"],
)
@teacher_required
def show_lab(lab_id):

    with SessionLocal() as db:

        lab = (
            db.query(Lab)
            .filter_by(id=lab_id)
            .first()
        )

        if lab is None:
            return "Lab not found", 404

        if lab.archived:
            flash(
                "Archived labs cannot be shown. Restore the lab first.",
                "warning",
            )

            return redirect(
                url_for("teacher_dashboard")
            )

        lab.visible = True

        db.commit()

        flash(
            f'Lab "{lab.name}" is now visible to students.',
            "success",
        )

        return redirect(
            url_for("teacher_dashboard")
        )
# ============================================================
# Teacher Lab Submissions
# ============================================================

@app.route(
    "/teacher/lab/<int:lab_id>/submissions"
)
@teacher_required
def teacher_lab_submissions(lab_id):

    with SessionLocal() as db:

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

        submissions = (
            db.query(Submission)
            .options(
                joinedload(
                    Submission.student
                ),
                joinedload(
                    Submission.grade
                ),
                joinedload(
                    Submission.lab
                ),
            )
            .filter(
                Submission.lab_id == lab.id,
                Submission.is_current == True,
            )
            .order_by(
                Submission.submitted_at.desc()
            )
            .all()
        )

        return render_template(
            "labs/submissions.html",
            lab=lab,
            submissions=submissions,
        )

# ============================================================
# Student Notifications
# ============================================================
# ============================================================
# Student Notifications
# ============================================================

@app.route("/notifications")
@login_required
def notifications():

    print("================================================")
    print("NOTIFICATION DEBUG")
    print("Session student_id:", session.get("student_id"))
    print("Session username:", session.get("github_username"))
    print("Session role:", session.get("role"))
    print("================================================")

    with SessionLocal() as db:

        student_id = session.get("student_id")

        notification_list = (
            db.query(Notification)
            .filter(
                Notification.student_id == student_id
            )
            .order_by(
                Notification.created_at.desc()
            )
            .all()
        )

        unread_count = (
            db.query(Notification)
            .filter(
                Notification.student_id == student_id,
                Notification.read == False,
            )
            .count()
        )

        print(
            "Notifications found:",
            len(notification_list)
        )

        print(
            "Unread notifications:",
            unread_count
        )

        for notification in notification_list:

            print(
                notification.id,
                notification.student_id,
                notification.title,
                notification.read,
            )

        return render_template(
            "notifications.html",
            notifications=notification_list,
            unread_count=unread_count,
        )

# ============================================================
# Mark Notification As Read
# ============================================================

@app.route(
    "/notifications/<int:notification_id>/read",
    methods=["POST"],
)
@login_required
def mark_notification_read(notification_id):

    with SessionLocal() as db:

        notification = (
            db.query(Notification)
            .filter_by(
                id=notification_id,
                student_id=session["student_id"],
            )
            .first()
        )

        if notification is None:
            return (
                "Notification not found",
                404,
            )

        if not notification.read:

            notification.read = True

            notification.read_at = (
                datetime.utcnow()
            )

            db.commit()

        if notification.submission_id:

            return redirect(
                url_for(
                    "submission_page",
                    submission_id=notification.submission_id,
                )
            )

        if notification.lab_id:

            return redirect(
                url_for(
                    "lab_page",
                    lab_id=notification.lab_id,
                )
            )

        return redirect(
            url_for("notifications")
        )

# ============================================================
# Mark All Notifications As Read
# ============================================================

@app.route(
    "/notifications/read-all",
    methods=["POST"],
)
@login_required
def mark_all_notifications_read():

    with SessionLocal() as db:

        now = datetime.utcnow()

        (
            db.query(Notification)
            .filter_by(
                student_id=session["student_id"],
                read=False,
            )
            .update(
                {
                    Notification.read: True,
                    Notification.read_at: now,
                },
                synchronize_session=False,
            )
        )

        db.commit()

        return redirect(
            url_for("notifications")
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

