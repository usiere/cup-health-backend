"""
Data transformation service for NLG optimization.
Transforms normalized DHIS2 data into flat, searchable structures for AI queries.
"""

import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
import logging

from models.dataset import DataValue, DataElement, Dataset
from models.organization_unit import OrganizationUnit, Period
from models.nlg_optimized import (
    DataValueFlat, DataElementSearchable, MonthlyAggregates,
    QuarterlyAggregates, NLGQueryCache
)

logger = logging.getLogger(__name__)

class NLGDataTransformer:
    """Transforms DHIS2 data for optimal NLG/AI querying."""

    def __init__(self, db: Session):
        self.db = db

    async def transform_all_data(self, connection_id: int = 1) -> Dict[str, Any]:
        """
        Run complete data transformation pipeline.
        """
        stats = {
            "start_time": datetime.now(),
            "flattened_records": 0,
            "searchable_elements": 0,
            "monthly_aggregates": 0,
            "quarterly_aggregates": 0,
            "errors": []
        }

        try:
            # 1. Create flattened data values
            logger.info("Starting data flattening process...")
            flattened_count = await self._create_flattened_data_values(connection_id)
            stats["flattened_records"] = flattened_count

            # 2. Create searchable data elements
            logger.info("Creating searchable data elements...")
            searchable_count = await self._create_searchable_data_elements(connection_id)
            stats["searchable_elements"] = searchable_count

            # 3. Generate monthly aggregates
            logger.info("Generating monthly aggregates...")
            monthly_count = await self._create_monthly_aggregates(connection_id)
            stats["monthly_aggregates"] = monthly_count

            # 4. Generate quarterly aggregates
            logger.info("Generating quarterly aggregates...")
            quarterly_count = await self._create_quarterly_aggregates(connection_id)
            stats["quarterly_aggregates"] = quarterly_count

            stats["end_time"] = datetime.now()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"Data transformation completed successfully: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error in data transformation: {str(e)}")
            stats["errors"].append(str(e))
            return stats

    async def _create_flattened_data_values(self, connection_id: int) -> int:
        """Create flattened, denormalized data values for fast AI queries."""

        # Clear existing flattened data for this connection
        self.db.query(DataValueFlat).filter(DataValueFlat.connection_id == connection_id).delete()

        # Query with all necessary joins
        query = self.db.query(
            DataValue,
            DataElement.name.label('data_element_name'),
            DataElement.display_name.label('data_element_display_name'),
            DataElement.value_type,
            DataElement.aggregation_type,
            Dataset.name.label('dataset_name'),
            OrganizationUnit.name.label('org_unit_name'),
            OrganizationUnit.display_name.label('org_unit_display_name'),
            OrganizationUnit.level.label('org_unit_level'),
            OrganizationUnit.path.label('org_unit_path'),
            OrganizationUnit.parent_name.label('parent_org_unit'),
            OrganizationUnit.coordinates.label('org_unit_coordinates'),
            Period.name.label('period_name'),
            Period.period_type,
            Period.start_date,
            Period.end_date
        ).join(
            DataElement, DataValue.data_element_id == DataElement.id
        ).join(
            Dataset, DataElement.dataset_id == Dataset.id
        ).join(
            OrganizationUnit, DataValue.org_unit_id == OrganizationUnit.id
        ).join(
            Period, DataValue.period_id == Period.id
        ).filter(
            Dataset.connection_id == connection_id
        )

        count = 0
        batch_size = 1000

        for offset in range(0, query.count(), batch_size):
            batch = query.offset(offset).limit(batch_size).all()

            flat_records = []
            for row in batch:
                data_value = row[0]  # DataValue object

                # Parse numeric value
                numeric_value = self._parse_numeric_value(data_value.value)

                # Extract time components
                year, month, quarter = self._extract_time_components(
                    row.period_name, row.period_type
                )

                # Create searchable text
                search_text = self._create_search_text(
                    row.data_element_name,
                    row.org_unit_name,
                    row.period_name,
                    row.dataset_name,
                    data_value.value
                )

                flat_record = DataValueFlat(
                    original_data_value_id=data_value.id,
                    connection_id=connection_id,

                    # Readable names
                    data_element_name=row.data_element_name,
                    data_element_display_name=row.data_element_display_name,
                    organization_unit_name=row.org_unit_name,
                    organization_unit_display_name=row.org_unit_display_name,
                    period_name=row.period_name,
                    dataset_name=row.dataset_name,

                    # Hierarchical context
                    org_unit_level=row.org_unit_level,
                    org_unit_path=row.org_unit_path,
                    parent_org_unit=row.parent_org_unit,
                    org_unit_coordinates=row.org_unit_coordinates,

                    # Time context
                    year=year,
                    month=month,
                    quarter=quarter,
                    period_type=row.period_type,
                    period_start_date=row.start_date,
                    period_end_date=row.end_date,

                    # Value data
                    value=data_value.value,
                    numeric_value=numeric_value,
                    value_type=row.value_type,
                    aggregation_type=row.aggregation_type,

                    # Category combinations
                    category_combo=data_value.category_option_combo,
                    attribute_option_combo=data_value.attribute_option_combo,

                    # Searchable text
                    search_text=search_text,

                    # DHIS2 references
                    dhis2_data_element_id=data_value.dhis2_data_element_id,
                    dhis2_org_unit_id=data_value.dhis2_org_unit_id,
                    dhis2_period_id=data_value.dhis2_period_id,

                    last_sync_at=datetime.now()
                )

                flat_records.append(flat_record)

            # Bulk insert batch
            self.db.bulk_save_objects(flat_records)
            self.db.commit()
            count += len(flat_records)

            logger.info(f"Processed {count} flattened records so far...")

        logger.info(f"Created {count} flattened data value records")
        return count

    async def _create_searchable_data_elements(self, connection_id: int) -> int:
        """Create enhanced searchable metadata for data elements."""

        # Clear existing searchable data for this connection
        self.db.query(DataElementSearchable).filter(
            DataElementSearchable.connection_id == connection_id
        ).delete()

        # Get all data elements for this connection
        data_elements = self.db.query(DataElement).join(
            Dataset, DataElement.dataset_id == Dataset.id
        ).filter(Dataset.connection_id == connection_id).all()

        searchable_records = []

        for element in data_elements:
            # Generate keywords from name
            keywords = self._extract_keywords(element.name, element.display_name)

            # Classify health domain and data category
            health_domain = self._classify_health_domain(element.name)
            data_category = self._classify_data_category(element.name)

            # Create searchable description
            description = self._create_element_description(element)

            searchable_record = DataElementSearchable(
                data_element_id=element.id,
                connection_id=connection_id,
                keywords=keywords,
                synonyms=self._generate_synonyms(element.name),
                category_tags=f"{health_domain},{data_category}",
                description=description,
                health_domain=health_domain,
                data_category=data_category,
                frequency=self._determine_frequency(element.name),
                search_popularity=0,
                data_quality_score=None  # To be calculated later
            )

            searchable_records.append(searchable_record)

        # Bulk insert
        self.db.bulk_save_objects(searchable_records)
        self.db.commit()

        logger.info(f"Created {len(searchable_records)} searchable data element records")
        return len(searchable_records)

    async def _create_monthly_aggregates(self, connection_id: int) -> int:
        """Create pre-computed monthly aggregates."""

        # Clear existing monthly aggregates
        self.db.query(MonthlyAggregates).filter(
            MonthlyAggregates.connection_id == connection_id
        ).delete()

        # Aggregate by data element, org unit, and month
        aggregation_query = text("""
            INSERT INTO monthly_aggregates (
                connection_id, data_element_name, org_unit_name, org_unit_level,
                year_month, year, month, total_value, average_value, min_value, max_value,
                count_values, count_non_zero, standard_deviation, median_value,
                completeness_rate, data_points_count, created_at
            )
            SELECT
                :connection_id,
                data_element_name,
                organization_unit_name,
                org_unit_level,
                CONCAT(year, '-', LPAD(month, 2, '0')) as year_month,
                year,
                month,
                SUM(CAST(numeric_value AS DECIMAL(15,2))) as total_value,
                AVG(CAST(numeric_value AS DECIMAL(15,2))) as average_value,
                MIN(CAST(numeric_value AS DECIMAL(15,2))) as min_value,
                MAX(CAST(numeric_value AS DECIMAL(15,2))) as max_value,
                COUNT(*) as count_values,
                SUM(CASE WHEN CAST(numeric_value AS DECIMAL(15,2)) > 0 THEN 1 ELSE 0 END) as count_non_zero,
                STDDEV(CAST(numeric_value AS DECIMAL(15,2))) as standard_deviation,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY CAST(numeric_value AS DECIMAL(15,2))) as median_value,
                (COUNT(*) * 100.0 / COUNT(*)) as completeness_rate,
                COUNT(*) as data_points_count,
                NOW()
            FROM data_values_flat
            WHERE connection_id = :connection_id
                AND numeric_value IS NOT NULL
                AND year IS NOT NULL
                AND month IS NOT NULL
            GROUP BY data_element_name, organization_unit_name, org_unit_level, year, month
            ORDER BY data_element_name, organization_unit_name, year, month
        """)

        result = self.db.execute(aggregation_query, {"connection_id": connection_id})
        self.db.commit()

        # Get count of created records
        count = self.db.query(MonthlyAggregates).filter(
            MonthlyAggregates.connection_id == connection_id
        ).count()

        # Calculate trends (percentage changes)
        await self._calculate_monthly_trends(connection_id)

        logger.info(f"Created {count} monthly aggregate records")
        return count

    async def _create_quarterly_aggregates(self, connection_id: int) -> int:
        """Create pre-computed quarterly aggregates."""

        # Clear existing quarterly aggregates
        self.db.query(QuarterlyAggregates).filter(
            QuarterlyAggregates.connection_id == connection_id
        ).delete()

        # Aggregate by data element, org unit, and quarter
        aggregation_query = text("""
            INSERT INTO quarterly_aggregates (
                connection_id, data_element_name, org_unit_name, org_unit_level,
                year_quarter, year, quarter, total_value, average_value, min_value, max_value,
                count_values, created_at
            )
            SELECT
                :connection_id,
                data_element_name,
                organization_unit_name,
                org_unit_level,
                CONCAT(year, '-', quarter) as year_quarter,
                year,
                quarter,
                SUM(CAST(numeric_value AS DECIMAL(15,2))) as total_value,
                AVG(CAST(numeric_value AS DECIMAL(15,2))) as average_value,
                MIN(CAST(numeric_value AS DECIMAL(15,2))) as min_value,
                MAX(CAST(numeric_value AS DECIMAL(15,2))) as max_value,
                COUNT(*) as count_values,
                NOW()
            FROM data_values_flat
            WHERE connection_id = :connection_id
                AND numeric_value IS NOT NULL
                AND year IS NOT NULL
                AND quarter IS NOT NULL
            GROUP BY data_element_name, organization_unit_name, org_unit_level, year, quarter
            ORDER BY data_element_name, organization_unit_name, year, quarter
        """)

        result = self.db.execute(aggregation_query, {"connection_id": connection_id})
        self.db.commit()

        # Get count of created records
        count = self.db.query(QuarterlyAggregates).filter(
            QuarterlyAggregates.connection_id == connection_id
        ).count()

        logger.info(f"Created {count} quarterly aggregate records")
        return count

    # Helper methods

    def _parse_numeric_value(self, value: str) -> Optional[float]:
        """Parse string value to numeric, handling various formats."""
        if not value:
            return None

        try:
            # Remove common non-numeric characters
            cleaned = re.sub(r'[^\d.-]', '', str(value))
            if cleaned:
                return float(cleaned)
        except (ValueError, TypeError):
            pass

        return None

    def _extract_time_components(self, period_name: str, period_type: str) -> tuple:
        """Extract year, month, quarter from period information."""
        year, month, quarter = None, None, None

        if not period_name:
            return year, month, quarter

        # Extract year (look for 4-digit year)
        year_match = re.search(r'20\d{2}', period_name)
        if year_match:
            year = int(year_match.group())

        # Extract month (for monthly periods)
        if period_type and 'month' in period_type.lower():
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }

            period_lower = period_name.lower()
            for month_name, month_num in month_names.items():
                if month_name in period_lower:
                    month = month_num
                    break

            # Also check for numeric month patterns like "202410"
            if not month and year:
                month_match = re.search(f'{year}(\\d{{2}})', period_name)
                if month_match:
                    month = int(month_match.group(1))

        # Determine quarter from month
        if month:
            quarter = f"Q{((month - 1) // 3) + 1}"

        return year, month, quarter

    def _create_search_text(self, data_element: str, org_unit: str,
                          period: str, dataset: str, value: str) -> str:
        """Create comprehensive searchable text."""
        components = [
            data_element or "",
            org_unit or "",
            period or "",
            dataset or "",
            str(value) if value else ""
        ]

        return " ".join(filter(None, components)).lower()

    def _extract_keywords(self, name: str, display_name: str = None) -> str:
        """Extract relevant keywords from data element names."""
        text = f"{name} {display_name or ''}".lower()

        # Remove common words and extract meaningful terms
        stopwords = {'the', 'of', 'and', 'or', 'in', 'at', 'to', 'for', 'with', 'by'}
        words = re.findall(r'\b\w+\b', text)
        keywords = [word for word in words if word not in stopwords and len(word) > 2]

        return ", ".join(set(keywords))

    def _classify_health_domain(self, name: str) -> str:
        """Classify data element into health domain."""
        name_lower = name.lower()

        if any(term in name_lower for term in ['malaria', 'tb', 'tuberculosis', 'hiv', 'aids']):
            return 'infectious_disease'
        elif any(term in name_lower for term in ['maternal', 'pregnancy', 'birth', 'delivery']):
            return 'maternal_health'
        elif any(term in name_lower for term in ['child', 'infant', 'immunization', 'vaccination']):
            return 'child_health'
        elif any(term in name_lower for term in ['nutrition', 'malnutrition', 'stunting']):
            return 'nutrition'
        else:
            return 'general_health'

    def _classify_data_category(self, name: str) -> str:
        """Classify data element by type of data."""
        name_lower = name.lower()

        if any(term in name_lower for term in ['cases', 'incidence', 'new']):
            return 'cases'
        elif any(term in name_lower for term in ['deaths', 'mortality', 'died']):
            return 'deaths'
        elif any(term in name_lower for term in ['coverage', 'rate', 'percentage']):
            return 'coverage'
        elif any(term in name_lower for term in ['population', 'total', 'number']):
            return 'population'
        else:
            return 'other'

    def _generate_synonyms(self, name: str) -> str:
        """Generate synonyms for data element names."""
        # Basic synonym mapping - could be enhanced with NLP libraries
        synonym_map = {
            'cases': 'incidents, occurrences, instances',
            'deaths': 'mortality, fatalities, deceased',
            'children': 'kids, minors, youth',
            'women': 'females, mothers',
            'men': 'males, fathers'
        }

        synonyms = []
        name_lower = name.lower()

        for term, synonym_list in synonym_map.items():
            if term in name_lower:
                synonyms.extend(synonym_list.split(', '))

        return ", ".join(set(synonyms))

    def _create_element_description(self, element: DataElement) -> str:
        """Create human-readable description for data element."""
        return f"{element.display_name or element.name} - {element.value_type or 'data'} collected for health monitoring and analysis."

    def _determine_frequency(self, name: str) -> str:
        """Determine typical collection frequency from name patterns."""
        name_lower = name.lower()

        if 'monthly' in name_lower:
            return 'monthly'
        elif 'quarterly' in name_lower:
            return 'quarterly'
        elif 'annual' in name_lower or 'yearly' in name_lower:
            return 'yearly'
        else:
            return 'variable'

    async def _calculate_monthly_trends(self, connection_id: int):
        """Calculate month-over-month trends for monthly aggregates."""

        # Update percentage changes using window functions
        trend_query = text("""
            UPDATE monthly_aggregates ma1
            SET previous_month_value = ma2.total_value,
                percentage_change = CASE
                    WHEN ma2.total_value > 0 THEN
                        ((ma1.total_value - ma2.total_value) / ma2.total_value) * 100
                    ELSE NULL
                END,
                absolute_change = ma1.total_value - ma2.total_value,
                trend_direction = CASE
                    WHEN ma1.total_value > ma2.total_value THEN 'increasing'
                    WHEN ma1.total_value < ma2.total_value THEN 'decreasing'
                    ELSE 'stable'
                END
            FROM monthly_aggregates ma2
            WHERE ma1.connection_id = :connection_id
                AND ma2.connection_id = :connection_id
                AND ma1.data_element_name = ma2.data_element_name
                AND ma1.org_unit_name = ma2.org_unit_name
                AND ma1.year = ma2.year
                AND ma1.month = ma2.month + 1
                OR (ma1.year = ma2.year + 1 AND ma1.month = 1 AND ma2.month = 12)
        """)

        self.db.execute(trend_query, {"connection_id": connection_id})
        self.db.commit()

        logger.info("Calculated monthly trends successfully")