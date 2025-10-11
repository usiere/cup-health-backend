from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from database import Base

class Query(Base):
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    natural_language_query = Column(Text, nullable=False)
    generated_sql = Column(Text, nullable=True)
    results = Column(JSON, nullable=True)
    execution_time = Column(Integer, nullable=True)  # in milliseconds
    status = Column(String, default="pending")  # pending, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())