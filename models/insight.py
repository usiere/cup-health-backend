from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean
from sqlalchemy.sql import func
from database import Base

class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    query_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    visualization_config = Column(JSON, nullable=True)
    is_shared = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())