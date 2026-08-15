import os
import smtplib

from email.message import EmailMessage


def send_grade_published_email(
    student_email,
    student_username,
    lab_name,
    score,
    feedback,
):
    """
    Send an email notifying a student that their grade
    has been published.
    """

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ["SMTP_USERNAME"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    sender_email = os.environ["SMTP_FROM"]

    # --------------------------------------------------------
    # Build email
    # --------------------------------------------------------

    message = EmailMessage()

    message["Subject"] = f"Grade published - {lab_name}"
    message["From"] = sender_email
    message["To"] = student_email

    feedback_text = feedback or "No feedback was provided."

    message.set_content(
        f"""Hello {student_username},

Your grade for the lab "{lab_name}" has been published.

Score: {score:.2f}/100

Teacher feedback:
{feedback_text}

Please log in to the Lab Grading System to view your complete grading results.

Best regards,
Lab Grading System
"""
    )

    # --------------------------------------------------------
    # Connect to SMTP server
    # --------------------------------------------------------

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