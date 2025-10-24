from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class OrganizationUnit(Base):
    __tablename__ = "organization_units"

    id = Column(Integer, primary_key=True, index=True)
    dhis2_id = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    level = Column(Integer, nullable=False)
    path = Column(String, nullable=True)  # DHIS2 hierarchy path
    parent_id = Column(String, nullable=True)  # DHIS2 parent ID
    parent_name = Column(String, nullable=True)
    coordinates = Column(JSON, nullable=True)  # Lat/long if available
    connection_id = Column(Integer, ForeignKey("dhis2_connections.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Period(Base):
    __tablename__ = "periods"

    id = Column(Integer, primary_key=True, index=True)
    dhis2_id = Column(String, nullable=False, unique=True, index=True)  # e.g., "202410"
    name = Column(String, nullable=False)  # e.g., "October 2024"
    display_name = Column(String, nullable=True)
    period_type = Column(String, nullable=False)  # Monthly, Yearly, etc.
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Indicator(Base):
    __tablename__ = "indicators"

    id = Column(Integer, primary_key=True, index=True)
    dhis2_id = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    numerator = Column(String, nullable=True)  # Formula
    denominator = Column(String, nullable=True)  # Formula
    indicator_type = Column(JSON, nullable=True)
    connection_id = Column(Integer, ForeignKey("dhis2_connections.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())