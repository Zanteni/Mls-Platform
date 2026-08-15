from .database import Base, engine
from .models import Student, Lab, Submission, Grade


Base.metadata.create_all(
    bind=engine
)

print("Database created successfully.")