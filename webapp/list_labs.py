from database import SessionLocal
from models import Lab


with SessionLocal() as session:

    labs = session.query(Lab).order_by(Lab.id).all()

    for lab in labs:
        print(
            f"{lab.id}: "
            f"{lab.name} — "
            f"{lab.description}"
        )