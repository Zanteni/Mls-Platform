from .database import SessionLocal
from .models import Lab


labs = [
    {
        "name": "lab1",
        "description": "Data preprocessing",
        "github_url": "https://github.com/MLs-labs/lab_0_data_preprocessing.git",
    },
    {
        "name": "lab2",
        "description": "Linear and logistic regression",
        "github_url": "https://github.com/MLs-labs/Lab-2-Lin_Regr-Log-Reg.git",
    },
    {
        "name": "lab3",
        "description": "Support vector machines",
        "github_url": "https://github.com/MLs-labs/lab-3-svm.git",
    },
]

with SessionLocal() as session:

    for lab_data in labs:
        existing = (
            session.query(Lab)
            .filter_by(name=lab_data["name"])
            .first()
        )

        if existing is None:
            session.add(
                Lab(**lab_data)
            )

    session.commit()

print("Labs seeded successfully.")