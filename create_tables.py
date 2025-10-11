from database import engine, Base
from models.dataset import Dataset, DataElement, DataValue

def create_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully!")

if __name__ == "__main__":
    create_tables()