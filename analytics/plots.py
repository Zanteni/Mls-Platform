from pathlib import Path

import matplotlib.pyplot as plt


def plot_skill_mastery(skill_results, output_dir):
    """Plot mastery percentage for each skill."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = skill_results.sort_values("mastery")

    plt.figure(figsize=(9, 5))

    plt.barh(
        data["skill"],
        data["mastery"] * 100,
    )

    plt.xlabel("Mastery (%)")
    plt.ylabel("Skill")
    plt.title("Skill Mastery Across the Class")
    plt.xlim(0, 100)

    for index, value in enumerate(data["mastery"] * 100):
        plt.text(
            value + 1,
            index,
            f"{value:.0f}%",
            va="center",
        )

    plt.tight_layout()

    path = output_dir / "skill_mastery.png"
    plt.savefig(path, dpi=150)
    plt.close()

    return path


def plot_skill_failures(skill_results, output_dir):
    """Plot number of students failing each skill."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = skill_results.sort_values("students_failed")

    plt.figure(figsize=(9, 5))

    plt.barh(
        data["skill"],
        data["students_failed"],
    )

    plt.xlabel("Students Failed")
    plt.ylabel("Skill")
    plt.title("Students Failing Each Skill")

    for index, value in enumerate(data["students_failed"]):
        plt.text(
            value + 0.05,
            index,
            str(int(value)),
            va="center",
        )

    plt.tight_layout()

    path = output_dir / "skill_failures.png"
    plt.savefig(path, dpi=150)
    plt.close()

    return path


def plot_student_scores(student_results, output_dir):
    """Plot score for each student."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = student_results.sort_values("score")

    plt.figure(figsize=(9, 5))

    plt.bar(
        data["student"],
        data["score"] * 100,
    )

    plt.xlabel("Student")
    plt.ylabel("Score (%)")
    plt.title("Student Scores")
    plt.ylim(0, 100)

    for index, value in enumerate(data["score"] * 100):
        plt.text(
            index,
            value + 2,
            f"{value:.0f}%",
            ha="center",
        )

    plt.tight_layout()

    path = output_dir / "student_scores.png"
    plt.savefig(path, dpi=150)
    plt.close()

    return path


# ---------------------------------------------------------
# NEW: STUDENT PROGRESSION
# ---------------------------------------------------------

def plot_student_progression(results_df, output_dir):
    """Plot each student's score progression across labs."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    for student in sorted(results_df["student"].unique()):

        student_df = results_df[
            results_df["student"] == student
        ].copy()

        # Sort labs naturally: lab1, lab2, lab3, ...
        student_df["lab_num"] = (
            student_df["lab"]
            .str.extract(r"(\d+)")
            .astype(int)
        )

        student_df = student_df.sort_values("lab_num")

        ax.plot(
            student_df["lab"],
            student_df["score"] * 100,
            marker="o",
            label=student,
        )

    ax.set_title("Student Progression Across Labs")
    ax.set_xlabel("Lab")
    ax.set_ylabel("Score (%)")
    ax.set_ylim(0, 105)

    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    path = output_dir / "student_progression.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)

    return path


# ---------------------------------------------------------
# GENERATE ALL PLOTS
# ---------------------------------------------------------

def generate_all_plots(
    results_df,
    student_results,
    skill_results,
    output_dir,
):
    """Generate all analytics plots."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {}

    paths["skill_mastery"] = plot_skill_mastery(
        skill_results,
        output_dir,
    )

    paths["skill_failures"] = plot_skill_failures(
        skill_results,
        output_dir,
    )

    paths["student_scores"] = plot_student_scores(
        student_results,
        output_dir,
    )

    # NEW
    paths["student_progression"] = plot_student_progression(
        results_df,
        output_dir,
    )

    return paths