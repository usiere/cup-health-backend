"""
RAG (Retrieval-Augmented Generation) Service for DHIS2 Data
Uses OpenAI API for intelligent query processing and response generation.
"""

import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text

from models.nlg_optimized import (
    DataValueFlat, DataElementSearchable, MonthlyAggregates,
    QuarterlyAggregates, NLGQueryCache
)

logger = logging.getLogger(__name__)

class RAGService:
    """Advanced RAG service for DHIS2 data queries using OpenAI."""

    def __init__(self, db: Session):
        self.db = db

        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.client = OpenAI(api_key=api_key)

        # Configuration
        self.embedding_model = "text-embedding-3-small"
        self.chat_model = "gpt-4o-mini"
        self.max_context_tokens = 15000  # Leave room for response
        self.similarity_threshold = 0.7

    async def process_query(self, query: str, connection_id: int = 1) -> Dict[str, Any]:
        """
        Process natural language query using RAG approach.

        1. Generate query embedding
        2. Retrieve relevant data context
        3. Generate AI response using retrieved context
        """
        try:
            # Check cache first
            cached_result = await self._check_cache(query, connection_id)
            if cached_result:
                logger.info(f"Returning cached result for query: {query[:50]}...")
                return cached_result

            start_time = datetime.now()

            # Step 1: Understand the query intent using OpenAI
            query_analysis = await self._analyze_query_intent(query)

            # Step 2: Retrieve relevant data based on intent
            relevant_data = await self._retrieve_relevant_data(
                query_analysis, connection_id
            )

            if not relevant_data["matches"]:
                return {
                    "status": "no_results",
                    "message": "I couldn't find any data matching your query in the DHIS2 system.",
                    "query": query,
                    "suggestions": await self._generate_query_suggestions(connection_id),
                    "execution_time": (datetime.now() - start_time).total_seconds()
                }

            # Step 3: Generate enhanced response using OpenAI
            ai_response = await self._generate_ai_response(
                query, query_analysis, relevant_data
            )

            result = {
                "status": "success",
                "query": query,
                "response": ai_response["response"],
                "insights": ai_response.get("insights", []),
                "data_summary": {
                    "total_records": len(relevant_data["matches"]),
                    "data_elements": list(set([m["data_element_name"] for m in relevant_data["matches"]])),
                    "time_range": relevant_data.get("time_range"),
                    "organizations": list(set([m["organization_unit_name"] for m in relevant_data["matches"]])),
                    "query_type": query_analysis.get("type", "general")
                },
                "detailed_data": relevant_data["matches"][:10],  # Limit for response size
                "execution_time": (datetime.now() - start_time).total_seconds()
            }

            # Cache the result
            await self._cache_result(query, result, connection_id)

            return result

        except Exception as e:
            logger.error(f"Error in RAG query processing: {str(e)}")
            return {
                "status": "error",
                "message": f"An error occurred while processing your query: {str(e)}",
                "query": query,
                "execution_time": (datetime.now() - datetime.now()).total_seconds()
            }

    async def _analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze query intent using OpenAI."""

        system_prompt = """You are an expert in analyzing healthcare data queries for DHIS2 systems.
        Analyze the user's query and extract the intent, entities, and requirements.

        Return a JSON response with:
        - type: "trend", "comparison", "summary", "filter", "specific_value"
        - entities: list of healthcare concepts mentioned (diseases, demographics, etc.)
        - time_period: extracted time references (years, months, quarters)
        - location: organization units or geographic references
        - metrics: specific measurements or indicators requested
        - intent_description: brief description of what the user wants

        DHIS2 Context:
        - Common data elements: children training, malaria cases, immunization coverage, mortality rates
        - Organization units: clinics, hospitals, districts
        - Time periods: monthly, quarterly, yearly data
        - Common queries: trends, totals, comparisons, geographic analysis
        """

        user_prompt = f"Analyze this DHIS2 data query: '{query}'"

        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

            # Parse JSON response
            analysis_text = response.choices[0].message.content

            # Try to extract JSON from response
            try:
                if '{' in analysis_text and '}' in analysis_text:
                    json_start = analysis_text.find('{')
                    json_end = analysis_text.rfind('}') + 1
                    json_str = analysis_text[json_start:json_end]
                    analysis = json.loads(json_str)
                else:
                    # Fallback: create basic analysis
                    analysis = {
                        "type": "general",
                        "entities": [],
                        "time_period": None,
                        "location": None,
                        "metrics": [],
                        "intent_description": analysis_text
                    }

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from OpenAI response: {analysis_text}")
                analysis = {
                    "type": "general",
                    "entities": [],
                    "time_period": None,
                    "location": None,
                    "metrics": [],
                    "intent_description": analysis_text
                }

            logger.info(f"Query analysis: {analysis}")
            return analysis

        except Exception as e:
            logger.error(f"Error in query analysis: {str(e)}")
            # Return basic analysis as fallback
            return {
                "type": "general",
                "entities": [],
                "time_period": None,
                "location": None,
                "metrics": [],
                "intent_description": "General query about DHIS2 data"
            }

    async def _retrieve_relevant_data(self, query_analysis: Dict, connection_id: int) -> Dict[str, Any]:
        """Retrieve relevant data based on query analysis."""

        results = {"matches": [], "time_range": None, "query_type": query_analysis.get("type", "general")}

        # Build base query
        base_query = self.db.query(DataValueFlat).filter(DataValueFlat.connection_id == connection_id)

        # Apply filters based on analysis
        filters = []

        # Time-based filtering
        time_period = query_analysis.get("time_period")
        if time_period:
            if "2024" in str(time_period):
                filters.append(DataValueFlat.year == 2024)
                results["time_range"] = "2024"
            # Add more time filtering logic as needed

        # Location-based filtering
        location = query_analysis.get("location")
        if location and isinstance(location, str):
            location_filters = []
            for loc in location.split():
                if len(loc) > 2:  # Avoid filtering on very short words
                    location_filters.append(DataValueFlat.organization_unit_name.contains(loc))
            if location_filters:
                filters.append(or_(*location_filters))

        # Entity-based filtering (health concepts)
        entities = query_analysis.get("entities", [])
        if entities:
            entity_filters = []
            for entity in entities:
                if isinstance(entity, str) and len(entity) > 2:
                    entity_filters.extend([
                        DataValueFlat.data_element_name.contains(entity),
                        DataValueFlat.search_text.contains(entity.lower())
                    ])
            if entity_filters:
                filters.append(or_(*entity_filters))

        # For trend queries, use monthly aggregates
        if query_analysis.get("type") == "trend":
            return await self._get_trend_data(query_analysis, connection_id)

        # Apply all filters
        if filters:
            base_query = base_query.filter(and_(*filters))

        # Execute query with proper ordering
        flat_results = base_query.order_by(DataValueFlat.year.desc(), DataValueFlat.month.desc()).limit(50).all()

        results["matches"] = [
            {
                "data_element_name": r.data_element_name,
                "organization_unit_name": r.organization_unit_name,
                "period": r.period_name,
                "value": r.numeric_value,
                "year": r.year,
                "month": r.month,
                "search_text": r.search_text,
                "type": "data_value"
            }
            for r in flat_results
        ]

        return results

    async def _get_trend_data(self, query_analysis: Dict, connection_id: int) -> Dict[str, Any]:
        """Get trend data from monthly aggregates."""

        results = {"matches": [], "time_range": None, "query_type": "trend"}

        # Query monthly aggregates
        monthly_query = self.db.query(MonthlyAggregates).filter(
            MonthlyAggregates.connection_id == connection_id
        )

        # Apply entity filters to trends
        entities = query_analysis.get("entities", [])
        if entities:
            entity_filters = []
            for entity in entities:
                if isinstance(entity, str) and len(entity) > 2:
                    entity_filters.append(MonthlyAggregates.data_element_name.contains(entity))
            if entity_filters:
                monthly_query = monthly_query.filter(or_(*entity_filters))

        monthly_results = monthly_query.order_by(MonthlyAggregates.year_month).all()

        results["matches"] = [
            {
                "data_element_name": r.data_element_name,
                "organization_unit_name": r.org_unit_name,
                "period": r.year_month,
                "value": r.total_value,
                "trend_direction": getattr(r, 'trend_direction', None),
                "percentage_change": getattr(r, 'percentage_change', None),
                "type": "monthly_aggregate"
            }
            for r in monthly_results
        ]

        return results

    async def _generate_ai_response(self, original_query: str, query_analysis: Dict, data: Dict) -> Dict[str, Any]:
        """Generate AI response using OpenAI with retrieved data context."""

        # Prepare data context for AI
        data_context = self._prepare_data_context(data)

        system_prompt = """You are a DHIS2 health data analyst expert. Provide clear, insightful responses about health data.

        Guidelines:
        - Be specific with numbers and statistics
        - Identify trends and patterns
        - Provide health insights when relevant
        - Use clear, professional language
        - Structure responses logically
        - Highlight significant findings
        - Suggest further analysis when appropriate

        Always include:
        1. Direct answer to the question
        2. Key statistics (totals, averages, trends)
        3. Notable patterns or insights
        4. Context about the timeframe and scope
        """

        user_prompt = f"""
        User Query: {original_query}

        Query Analysis: {json.dumps(query_analysis, indent=2)}

        Available Data Context:
        {data_context}

        Provide a comprehensive analysis and response to the user's query based on this DHIS2 health data.
        """

        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )

            ai_response = response.choices[0].message.content

            # Generate insights
            insights = await self._extract_insights(data, query_analysis)

            return {
                "response": ai_response,
                "insights": insights
            }

        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            # Fallback to basic response
            return {
                "response": f"I found {len(data['matches'])} data points related to your query. The data includes information from various health facilities and time periods.",
                "insights": []
            }

    def _prepare_data_context(self, data: Dict) -> str:
        """Prepare data context string for AI."""

        matches = data.get("matches", [])
        if not matches:
            return "No data found."

        # Summarize the data
        context_lines = [
            f"Total Records: {len(matches)}",
            f"Query Type: {data.get('query_type', 'general')}",
            f"Time Range: {data.get('time_range', 'Various periods')}"
        ]

        # Data elements summary
        data_elements = list(set([m["data_element_name"] for m in matches]))
        context_lines.append(f"Data Elements: {', '.join(data_elements[:5])}{'...' if len(data_elements) > 5 else ''}")

        # Organizations summary
        organizations = list(set([m["organization_unit_name"] for m in matches]))
        context_lines.append(f"Organizations: {', '.join(organizations[:3])}{'...' if len(organizations) > 3 else ''}")

        # Statistical summary
        values = [m["value"] for m in matches if m.get("value")]
        if values:
            context_lines.extend([
                f"Total Value: {sum(values):,.0f}",
                f"Average Value: {sum(values)/len(values):,.1f}",
                f"Value Range: {min(values):,.0f} - {max(values):,.0f}"
            ])

        # Sample data points (first 5)
        context_lines.append("\nSample Data Points:")
        for i, match in enumerate(matches[:5]):
            period = match.get("period", "Unknown period")
            value = match.get("value", 0)
            context_lines.append(
                f"{i+1}. {match['data_element_name']} at {match['organization_unit_name']} "
                f"({period}): {value:,.0f}"
            )

        return "\n".join(context_lines)

    async def _extract_insights(self, data: Dict, query_analysis: Dict) -> List[str]:
        """Extract key insights from the data."""

        insights = []
        matches = data.get("matches", [])

        if not matches:
            return insights

        # Statistical insights
        values = [m["value"] for m in matches if m.get("value")]
        if values:
            if max(values) > sum(values) / len(values) * 3:
                insights.append("There are significant outliers in the data with much higher values than average")

            if len(set([m["organization_unit_name"] for m in matches])) > 1:
                insights.append("Data spans multiple health facilities")

        # Trend insights
        if data.get("query_type") == "trend":
            trend_values = [m for m in matches if m.get("percentage_change")]
            if trend_values:
                positive_trends = [t for t in trend_values if t["percentage_change"] > 0]
                if len(positive_trends) > len(trend_values) * 0.6:
                    insights.append("Most indicators show positive trends over time")

        # Time period insights
        years = list(set([m["year"] for m in matches if m.get("year")]))
        if len(years) > 1:
            insights.append(f"Data covers {len(years)} different years: {', '.join(map(str, sorted(years)))}")

        return insights

    async def _generate_query_suggestions(self, connection_id: int) -> List[str]:
        """Generate helpful query suggestions based on available data."""

        # Get available data elements
        data_elements = self.db.query(DataValueFlat.data_element_name).filter(
            DataValueFlat.connection_id == connection_id
        ).distinct().limit(5).all()

        suggestions = [
            "Try asking about specific health indicators like 'children trained' or 'immunization coverage'",
            "Ask for trends over time, like 'show monthly trends for 2024'",
            "Request data for specific facilities or locations"
        ]

        # Add specific suggestions based on available data
        if data_elements:
            element_names = [elem[0] for elem in data_elements]
            for element in element_names[:2]:
                suggestions.append(f"Ask about '{element}' data")

        return suggestions

    async def _check_cache(self, query: str, connection_id: int) -> Optional[Dict[str, Any]]:
        """Check if query result is cached."""

        query_hash = hashlib.md5(f"{query}_{connection_id}".encode()).hexdigest()

        cached = self.db.query(NLGQueryCache).filter(
            and_(
                NLGQueryCache.query_hash == query_hash,
                NLGQueryCache.connection_id == connection_id,
                NLGQueryCache.is_valid == True
            )
        ).first()

        if cached:
            # Update hit count and last accessed
            cached.hit_count += 1
            cached.last_accessed = datetime.now()
            self.db.commit()

            return cached.response_data

        return None

    async def _cache_result(self, query: str, result: Dict[str, Any], connection_id: int):
        """Cache query result for faster future responses."""

        query_hash = hashlib.md5(f"{query}_{connection_id}".encode()).hexdigest()

        # Check if already exists
        existing = self.db.query(NLGQueryCache).filter(
            NLGQueryCache.query_hash == query_hash
        ).first()

        if existing:
            # Update existing cache
            existing.response_data = result
            existing.hit_count = 1
            existing.last_accessed = datetime.now()
            existing.is_valid = True
        else:
            # Create new cache entry
            cache_entry = NLGQueryCache(
                connection_id=connection_id,
                query_text=query,
                query_hash=query_hash,
                normalized_query=query.lower().strip(),
                response_data=result,
                execution_time_ms=int(result.get("execution_time", 0) * 1000),
                hit_count=1,
                last_accessed=datetime.now(),
                is_valid=True
            )
            self.db.add(cache_entry)

        self.db.commit()