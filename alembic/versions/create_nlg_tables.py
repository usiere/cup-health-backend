"""Create NLG-optimized tables and indexes

Revision ID: nlg_optimization_001
Revises:
Create Date: 2024-12-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = 'nlg_optimization_001'
down_revision = None
depends_on = None

def upgrade():
    """Create NLG-optimized tables and performance indexes."""

    # Create indexes for existing tables first
    op.execute(text("""
        -- Performance indexes for data_values table
        CREATE INDEX IF NOT EXISTS idx_data_values_dhis2_refs
        ON data_values (dhis2_data_element_id, dhis2_org_unit_id, dhis2_period_id);

        CREATE INDEX IF NOT EXISTS idx_data_values_element_org_period
        ON data_values (data_element_id, org_unit_id, period_id);

        -- Performance indexes for organization_units
        CREATE INDEX IF NOT EXISTS idx_org_units_level_parent
        ON organization_units (level, parent_id);

        CREATE INDEX IF NOT EXISTS idx_org_units_path
        ON organization_units USING GIN(to_tsvector('english', path));

        -- Performance indexes for periods
        CREATE INDEX IF NOT EXISTS idx_periods_type_name
        ON periods (period_type, name);

        -- Performance indexes for data_elements
        CREATE INDEX IF NOT EXISTS idx_data_elements_name_search
        ON data_elements USING GIN(to_tsvector('english', name || ' ' || COALESCE(display_name, '')));

        CREATE INDEX IF NOT EXISTS idx_data_elements_value_type
        ON data_elements (value_type, aggregation_type);
    """))

    # Create specific indexes for the new NLG tables after they're created by SQLAlchemy
    op.execute(text("""
        -- Full-text search indexes for data_values_flat
        CREATE INDEX IF NOT EXISTS idx_data_values_flat_search_text
        ON data_values_flat USING GIN(to_tsvector('english', search_text));

        CREATE INDEX IF NOT EXISTS idx_data_values_flat_names_search
        ON data_values_flat USING GIN(to_tsvector('english',
            data_element_name || ' ' ||
            organization_unit_name || ' ' ||
            period_name || ' ' ||
            dataset_name
        ));

        -- Performance indexes for common query patterns
        CREATE INDEX IF NOT EXISTS idx_data_values_flat_element_org_period
        ON data_values_flat (data_element_name, organization_unit_name, period_name);

        CREATE INDEX IF NOT EXISTS idx_data_values_flat_time_queries
        ON data_values_flat (year, month, quarter, period_type);

        CREATE INDEX IF NOT EXISTS idx_data_values_flat_geographic
        ON data_values_flat (org_unit_level, parent_org_unit);

        CREATE INDEX IF NOT EXISTS idx_data_values_flat_numeric_values
        ON data_values_flat (numeric_value) WHERE numeric_value IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_data_values_flat_connection_time
        ON data_values_flat (connection_id, year, month);

        -- Composite index for trend analysis
        CREATE INDEX IF NOT EXISTS idx_data_values_flat_trends
        ON data_values_flat (data_element_name, organization_unit_name, year, month, numeric_value);

        -- Full-text search for data_elements_searchable
        CREATE INDEX IF NOT EXISTS idx_searchable_elements_keywords
        ON data_elements_searchable USING GIN(to_tsvector('english', keywords));

        CREATE INDEX IF NOT EXISTS idx_searchable_elements_description
        ON data_elements_searchable USING GIN(to_tsvector('english', description));

        CREATE INDEX IF NOT EXISTS idx_searchable_elements_categories
        ON data_elements_searchable (health_domain, data_category);

        CREATE INDEX IF NOT EXISTS idx_searchable_elements_popularity
        ON data_elements_searchable (search_popularity DESC);

        -- Indexes for monthly_aggregates
        CREATE INDEX IF NOT EXISTS idx_monthly_agg_element_org_time
        ON monthly_aggregates (data_element_name, org_unit_name, year_month);

        CREATE INDEX IF NOT EXISTS idx_monthly_agg_time_range
        ON monthly_aggregates (year, month);

        CREATE INDEX IF NOT EXISTS idx_monthly_agg_trends
        ON monthly_aggregates (data_element_name, percentage_change)
        WHERE percentage_change IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_monthly_agg_values
        ON monthly_aggregates (total_value, average_value)
        WHERE total_value IS NOT NULL;

        -- Indexes for quarterly_aggregates
        CREATE INDEX IF NOT EXISTS idx_quarterly_agg_element_org_time
        ON quarterly_aggregates (data_element_name, org_unit_name, year_quarter);

        CREATE INDEX IF NOT EXISTS idx_quarterly_agg_time_range
        ON quarterly_aggregates (year, quarter);

        -- Indexes for NLG query cache
        CREATE INDEX IF NOT EXISTS idx_nlg_cache_hash
        ON nlg_query_cache (query_hash);

        CREATE INDEX IF NOT EXISTS idx_nlg_cache_popularity
        ON nlg_query_cache (hit_count DESC, last_accessed DESC);

        CREATE INDEX IF NOT EXISTS idx_nlg_cache_validity
        ON nlg_query_cache (is_valid, expires_at);

        CREATE INDEX IF NOT EXISTS idx_nlg_cache_query_search
        ON nlg_query_cache USING GIN(to_tsvector('english', query_text));
    """))

    # Create materialized views for common aggregations
    op.execute(text("""
        -- Materialized view for data summary by organization unit
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_org_unit_data_summary AS
        SELECT
            connection_id,
            organization_unit_name,
            org_unit_level,
            parent_org_unit,
            COUNT(DISTINCT data_element_name) as unique_data_elements,
            COUNT(*) as total_data_points,
            COUNT(CASE WHEN numeric_value > 0 THEN 1 END) as non_zero_values,
            MIN(year) as earliest_year,
            MAX(year) as latest_year,
            AVG(numeric_value) as avg_numeric_value,
            SUM(numeric_value) as total_numeric_value
        FROM data_values_flat
        WHERE numeric_value IS NOT NULL
        GROUP BY connection_id, organization_unit_name, org_unit_level, parent_org_unit;

        -- Index for the materialized view
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_org_unit_summary_unique
        ON mv_org_unit_data_summary (connection_id, organization_unit_name);

        -- Materialized view for data element popularity
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_data_element_popularity AS
        SELECT
            connection_id,
            data_element_name,
            COUNT(*) as usage_count,
            COUNT(DISTINCT organization_unit_name) as org_units_count,
            COUNT(DISTINCT CONCAT(year, '-', month)) as time_periods_count,
            AVG(numeric_value) as avg_value,
            MAX(last_sync_at) as last_updated
        FROM data_values_flat
        WHERE numeric_value IS NOT NULL
        GROUP BY connection_id, data_element_name;

        -- Index for the materialized view
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_element_popularity_unique
        ON mv_data_element_popularity (connection_id, data_element_name);
    """))

def downgrade():
    """Drop NLG-optimized tables and indexes."""

    # Drop materialized views
    op.execute(text("""
        DROP MATERIALIZED VIEW IF EXISTS mv_org_unit_data_summary;
        DROP MATERIALIZED VIEW IF EXISTS mv_data_element_popularity;
    """))

    # Drop custom indexes
    op.execute(text("""
        -- Drop indexes for data_values_flat
        DROP INDEX IF EXISTS idx_data_values_flat_search_text;
        DROP INDEX IF EXISTS idx_data_values_flat_names_search;
        DROP INDEX IF EXISTS idx_data_values_flat_element_org_period;
        DROP INDEX IF EXISTS idx_data_values_flat_time_queries;
        DROP INDEX IF EXISTS idx_data_values_flat_geographic;
        DROP INDEX IF EXISTS idx_data_values_flat_numeric_values;
        DROP INDEX IF EXISTS idx_data_values_flat_connection_time;
        DROP INDEX IF EXISTS idx_data_values_flat_trends;

        -- Drop indexes for data_elements_searchable
        DROP INDEX IF EXISTS idx_searchable_elements_keywords;
        DROP INDEX IF EXISTS idx_searchable_elements_description;
        DROP INDEX IF EXISTS idx_searchable_elements_categories;
        DROP INDEX IF EXISTS idx_searchable_elements_popularity;

        -- Drop indexes for monthly_aggregates
        DROP INDEX IF EXISTS idx_monthly_agg_element_org_time;
        DROP INDEX IF EXISTS idx_monthly_agg_time_range;
        DROP INDEX IF EXISTS idx_monthly_agg_trends;
        DROP INDEX IF EXISTS idx_monthly_agg_values;

        -- Drop indexes for quarterly_aggregates
        DROP INDEX IF EXISTS idx_quarterly_agg_element_org_time;
        DROP INDEX IF EXISTS idx_quarterly_agg_time_range;

        -- Drop indexes for nlg_query_cache
        DROP INDEX IF EXISTS idx_nlg_cache_hash;
        DROP INDEX IF EXISTS idx_nlg_cache_popularity;
        DROP INDEX IF EXISTS idx_nlg_cache_validity;
        DROP INDEX IF EXISTS idx_nlg_cache_query_search;

        -- Drop performance indexes on existing tables
        DROP INDEX IF EXISTS idx_data_values_dhis2_refs;
        DROP INDEX IF EXISTS idx_data_values_element_org_period;
        DROP INDEX IF EXISTS idx_org_units_level_parent;
        DROP INDEX IF EXISTS idx_org_units_path;
        DROP INDEX IF EXISTS idx_periods_type_name;
        DROP INDEX IF EXISTS idx_data_elements_name_search;
        DROP INDEX IF EXISTS idx_data_elements_value_type;
    """))