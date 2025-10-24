from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class DataValueFlat(Base):
    """
    Denormalized table optimized for NLG/AI queries.
    Contains flattened data with human-readable names and searchable text.
    """
    __tablename__ = "data_values_flat"

    id = Column(Integer, primary_key=True, index=True)

    # Original references
    original_data_value_id = Column(Integer, ForeignKey("data_values.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("dhis2_connections.id"), nullable=False)

    # Human-readable names (not IDs)
    data_element_name = Column(String, nullable=False, index=True)
    data_element_display_name = Column(String, nullable=True)
    organization_unit_name = Column(String, nullable=False, index=True)
    organization_unit_display_name = Column(String, nullable=True)
    period_name = Column(String, nullable=False, index=True)
    dataset_name = Column(String, nullable=False, index=True)

    # Hierarchical context for geographic queries
    org_unit_level = Column(Integer, nullable=True, index=True)
    org_unit_path = Column(String, nullable=True)  # "Country > Region > District"
    parent_org_unit = Column(String, nullable=True, index=True)
    org_unit_coordinates = Column(JSON, nullable=True)  # Lat/long if available

    # Time context for temporal queries
    year = Column(Integer, nullable=True, index=True)
    month = Column(Integer, nullable=True, index=True)
    quarter = Column(String, nullable=True, index=True)  # "Q1", "Q2", etc.
    period_type = Column(String, nullable=False, index=True)  # "Monthly", "Yearly", etc.
    period_start_date = Column(String, nullable=True)
    period_end_date = Column(String, nullable=True)

    # Value with metadata
    value = Column(String, nullable=False)
    numeric_value = Column(Float, nullable=True, index=True)  # Parsed numeric values
    value_type = Column(String, nullable=True)  # "NUMBER", "TEXT", etc.
    aggregation_type = Column(String, nullable=True)  # "SUM", "AVERAGE", etc.

    # Category combinations for detailed analysis
    category_combo = Column(JSON, nullable=True)
    attribute_option_combo = Column(String, nullable=True)

    # Searchable text for NLG (concatenated searchable content)
    search_text = Column(Text, nullable=True, index=True)

    # DHIS2 references for API calls
    dhis2_data_element_id = Column(String, nullable=False, index=True)
    dhis2_org_unit_id = Column(String, nullable=False, index=True)
    dhis2_period_id = Column(String, nullable=False, index=True)

    # Performance and tracking fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

class DataElementSearchable(Base):
    """
    Enhanced searchable metadata for data elements to support NLG queries.
    Contains keywords, synonyms, and semantic information.
    """
    __tablename__ = "data_elements_searchable"

    id = Column(Integer, primary_key=True, index=True)
    data_element_id = Column(Integer, ForeignKey("data_elements.id"), nullable=False, unique=True)
    connection_id = Column(Integer, ForeignKey("dhis2_connections.id"), nullable=False)

    # NLG-friendly fields
    keywords = Column(Text, nullable=True)  # "malaria, cases, reported, monthly, surveillance"
    synonyms = Column(Text, nullable=True)  # Alternative names and terms
    category_tags = Column(Text, nullable=True)  # "disease, surveillance, maternal_health, immunization"
    description = Column(Text, nullable=True)  # Human-readable description
    context_info = Column(Text, nullable=True)  # Additional context for AI understanding

    # Semantic search support
    embedding_vector = Column(JSON, nullable=True)  # Store embeddings for similarity search
    embedding_model = Column(String, nullable=True)  # Track which model generated embeddings

    # Classification for better query routing
    health_domain = Column(String, nullable=True, index=True)  # "maternal_health", "infectious_disease", etc.
    data_category = Column(String, nullable=True, index=True)  # "cases", "deaths", "coverage", etc.
    frequency = Column(String, nullable=True)  # How often this data is typically collected

    # Quality and relevance scores
    search_popularity = Column(Integer, default=0)  # Track how often this element is queried
    data_quality_score = Column(Float, nullable=True)  # Completeness/accuracy score

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class MonthlyAggregates(Base):
    """
    Pre-computed monthly aggregates for faster query response.
    Supports trend analysis and comparative queries.
    """
    __tablename__ = "monthly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("dhis2_connections.id"), nullable=False)

    # Grouping dimensions
    data_element_name = Column(String, nullable=False, index=True)
    org_unit_name = Column(String, nullable=False, index=True)
    org_unit_level = Column(Integer, nullable=True, index=True)
    year_month = Column(String, nullable=False, index=True)  # "2024-10"
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)

    # Aggregated values
    total_value = Column(Float, nullable=True)
    average_value = Column(Float, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    count_values = Column(Integer, default=0)
    count_non_zero = Column(Integer, default=0)

    # Trend calculations
    previous_month_value = Column(Float, nullable=True)
    percentage_change = Column(Float, nullable=True)
    absolute_change = Column(Float, nullable=True)
    trend_direction = Column(String, nullable=True)  # "increasing", "decreasing", "stable"

    # Statistical measures
    standard_deviation = Column(Float, nullable=True)
    variance = Column(Float, nullable=True)
    median_value = Column(Float, nullable=True)

    # Quality indicators
    completeness_rate = Column(Float, nullable=True)  # Percentage of expected values present
    data_points_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class QuarterlyAggregates(Base):
    """
    Pre-computed quarterly aggregates for quarterly trend analysis.
    """
    __tablename__ = "quarterly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("dhis2_connections.id"), nullable=False)

    # Grouping dimensions
    data_element_name = Column(String, nullable=False, index=True)
    org_unit_name = Column(String, nullable=False, index=True)
    org_unit_level = Column(Integer, nullable=True, index=True)
    year_quarter = Column(String, nullable=False, index=True)  # "2024-Q3"
    year = Column(Integer, nullable=False, index=True)
    quarter = Column(String, nullable=False, index=True)  # "Q1", "Q2", "Q3", "Q4"

    # Aggregated values
    total_value = Column(Float, nullable=True)
    average_value = Column(Float, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    count_values = Column(Integer, default=0)

    # Trend calculations
    previous_quarter_value = Column(Float, nullable=True)
    year_over_year_change = Column(Float, nullable=True)
    percentage_change = Column(Float, nullable=True)
    trend_direction = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class NLGQueryCache(Base):
    """
    Cache frequently asked NLG queries for better performance.
    """
    __tablename__ = "nlg_query_cache"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("dhis2_connections.id"), nullable=False)

    # Query information
    query_text = Column(Text, nullable=False)  # Original user query
    query_hash = Column(String, nullable=False, unique=True, index=True)  # Hash for quick lookup
    normalized_query = Column(Text, nullable=True)  # Cleaned/normalized version

    # Response information
    response_data = Column(JSON, nullable=False)  # Cached response
    response_metadata = Column(JSON, nullable=True)  # Additional metadata

    # Performance tracking
    execution_time_ms = Column(Integer, nullable=True)
    hit_count = Column(Integer, default=1)  # How many times this query was requested
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())

    # Cache management
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_valid = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())