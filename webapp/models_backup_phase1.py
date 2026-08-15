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


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    github_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # ----------------------------------------------------
    # Launch state
    # ----------------------------------------------------

    launched: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # ----------------------------------------------------
    # Submission window
    # ----------------------------------------------------

    submission_open: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    submission_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="lab",
    )


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