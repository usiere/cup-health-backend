from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from database import Base

class DHIS2Connection(Base):
    __tablename__ = "dhis2_connections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password_encrypted = Column(Text, nullable=False)
    organization_id = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())