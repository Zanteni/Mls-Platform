from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    github_username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    github_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        default="student",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="student",
    )

    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )

class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    # ========================================================
    # Identity
    # ========================================================

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )

    # Stable URL-friendly identifier.
    # Example: "lab-1-data-preprocessing"
    slug: Mapped[str | None] = mapped_column(
        String(150),
        unique=True,
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ========================================================
    # Assignment
    # ========================================================

    github_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # ========================================================
    # Lab organization
    # ========================================================

    # Used to control the order in which labs appear.
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Optional grouping/category.
    # Later this can become a separate LabCategory table.
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Allows the teacher to hide/archive a lab without deleting
    # all its submissions and grades.
    archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Allows a lab to exist in the database without appearing
    # to students yet.
    visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # ========================================================
    # Launch state
    # ========================================================

    launched: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # ========================================================
    # Submission window
    # ========================================================

    submission_open: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    submission_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ========================================================
    # Learning content
    # ========================================================

    # Optional official solution.
    #
    # For now we store a URL/path.
    # Later we can create a dedicated LabSolution table.
    solution_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # Optional explanation video.
    #
    # Could point to YouTube, Vimeo, local storage, etc.
    # Later this can become a dedicated LabVideo table.
    video_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # Optional teacher notes / explanation visible
    # on the lab detail page.
    teacher_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ========================================================
    # Timestamps
    # ========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # ========================================================
    # Relationships
    # ========================================================

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="lab",
    )

# ============================================================
# Notifications
# ============================================================

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    # --------------------------------------------------------
    # Recipient
    # --------------------------------------------------------

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False,
    )

    # --------------------------------------------------------
    # Optional related objects
    # --------------------------------------------------------

    lab_id: Mapped[int | None] = mapped_column(
        ForeignKey("labs.id"),
        nullable=True,
    )

    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id"),
        nullable=True,
    )

    # --------------------------------------------------------
    # Notification content
    # --------------------------------------------------------

    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # --------------------------------------------------------
    # Read state
    # --------------------------------------------------------

    read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    student: Mapped["Student"] = relationship()

    lab: Mapped["Lab | None"] = relationship()

    submission: Mapped["Submission | None"] = relationship()

class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False,
    )

    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id"),
        nullable=False,
    )

    repo_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="submitted",
    )

    # ========================================================
    # Relationships
    # ========================================================

    student: Mapped["Student"] = relationship(
        back_populates="submissions",
    )

    lab: Mapped["Lab"] = relationship(
        back_populates="submissions",
    )

    grade: Mapped["Grade | None"] = relationship(
        back_populates="submission",
        uselist=False,
    )

    # ========================================================
    # Submission Attempts
    # ========================================================

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # ========================================================
    # Immutable Repository Snapshot
    # ========================================================

    snapshot_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    commit_sha: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # ========================================================
    # Current Attempt
    # ========================================================

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # ========================================================
    # Resubmission Permission
    # ========================================================

    # Teacher has approved another submission
    resubmission_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Student has requested permission to resubmit
    resubmission_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Message shown to the student after teacher decision
    resubmission_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,

    )
    resubmission_rejections: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    resubmission_blocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id"),
        unique=True,
        nullable=False,
    )

    automatic_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    teacher_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    submission: Mapped["Submission"] = relationship(
        back_populates="grade",
    )

    notebooks: Mapped[list["NotebookResult"]] = relationship(
        back_populates="grade",
        cascade="all, delete-orphan",
    )


class NotebookResult(Base):
    __tablename__ = "notebook_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    grade_id: Mapped[int] = mapped_column(
        ForeignKey("grades.id"),
        nullable=False,
    )

    notebook_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    grade: Mapped["Grade"] = relationship(
        back_populates="notebooks",
    )

    checks: Mapped[list["CheckResult"]] = relationship(
        back_populates="notebook",
        cascade="all, delete-orphan",
    )


class CheckResult(Base):
    __tablename__ = "check_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    notebook_result_id: Mapped[int] = mapped_column(
        ForeignKey("notebook_results.id"),
        nullable=False,
    )

    check_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notebook: Mapped["NotebookResult"] = relationship(
        back_populates="checks",
    )