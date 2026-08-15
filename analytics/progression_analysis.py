import pandas as pd


def analyze_progression(results_df):
    """
    Analyze student score progression across labs.

    Returns one row per student/lab with:
        - score
        - previous_score
        - score_change
        - trend
    """

    if results_df.empty:
        return pd.DataFrame(
            columns=[
                "student",
                "lab",
                "score",
                "previous_score",
                "score_change",
                "trend",
            ]
        )

    # Keep one result per student/lab/notebook.
    results = (
        results_df
        .drop_duplicates(
            subset=["student", "lab", "notebook"],
            keep="last",
        )
        .copy()
    )

    # Sort labs naturally: lab1, lab2, lab3, ...
    results["_lab_number"] = (
        results["lab"]
        .astype(str)
        .str.extract(r"(\d+)", expand=False)
        .fillna(0)
        .astype(int)
    )

    results = results.sort_values(
        ["student", "_lab_number", "lab"]
    )

    # Previous lab score for each student.
    results["previous_score"] = (
        results
        .groupby("student")["score"]
        .shift(1)
    )

    # Improvement since previous lab.
    results["score_change"] = (
        results["score"] - results["previous_score"]
    )

    def get_trend(change):
        if pd.isna(change):
            return "first lab"

        if change > 0:
            return "improving"

        if change < 0:
            return "declining"

        return "stable"

    results["trend"] = results["score_change"].apply(get_trend)

    return (
        results[
            [
                "student",
                "lab",
                "score",
                "previous_score",
                "score_change",
                "trend",
            ]
        ]
        .reset_index(drop=True)
    )


def print_progression(progression_df):
    """
    Print a readable progression report for each student.
    """

    if progression_df.empty:
        print("No progression data available.")
        return

    print("\n" + "=" * 60)
    print("STUDENT PROGRESSION")
    print("=" * 60)

    for student, group in progression_df.groupby("student"):

        print(f"\n{student}")

        for _, row in group.iterrows():

            score = row["score"]

            if pd.isna(row["previous_score"]):
                print(
                    f"  {row['lab']:<10} "
                    f"{score:.0%}   "
                    f"(first lab)"
                )
            else:
                change = row["score_change"]

                print(
                    f"  {row['lab']:<10} "
                    f"{score:.0%}   "
                    f"{change:+.0%}   "
                    f"{row['trend']}"
                )