from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    dhis2_id = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    period_type = Column(String, nullable=False)
    category_combo = Column(JSON, nullable=True)
    connection_id = Column(Integer, ForeignKey("dhis2_connections.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    data_elements = relationship("DataElement", back_populates="dataset", cascade="all, delete-orphan")

class DataElement(Base):
    __tablename__ = "data_elements"

    id = Column(Integer, primary_key=True, index=True)
    dhis2_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    value_type = Column(String, nullable=True)
    domain_type = Column(String, nullable=True)
    aggregation_type = Column(String, nullable=True)
    category_combo = Column(JSON, nullable=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    dataset = relationship("Dataset", back_populates="data_elements")

class DataValue(Base):
    __tablename__ = "data_values"

    id = Column(Integer, primary_key=True, index=True)
    data_element_id = Column(Integer, ForeignKey("data_elements.id"), nullable=False)
    org_unit_id = Column(Integer, ForeignKey("organization_units.id"), nullable=False)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=False)
    value = Column(String, nullable=False)
    # DHIS2 specific fields
    dhis2_data_element_id = Column(String, nullable=False, index=True)
    dhis2_org_unit_id = Column(String, nullable=False, index=True)
    dhis2_period_id = Column(String, nullable=False, index=True)
    attribute_option_combo = Column(String, nullable=True)  # DHIS2 category combinations
    category_option_combo = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    data_element = relationship("DataElement")
    # Note: org_unit and period relationships will be added after importing the models