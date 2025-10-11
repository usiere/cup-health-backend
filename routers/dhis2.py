from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.dataset import Dataset, DataElement, DataValue
from models.dhis2_connection import DHIS2Connection
import httpx
import asyncio

router = APIRouter()

# DHIS2 public test instance configuration
TEST_DHIS2_BASE_URL = "https://play.im.dhis2.org/stable-2-42-2"
TEST_DHIS2_USERNAME = "admin"
TEST_DHIS2_PASSWORD = "district"

@router.get("/test-connection")
async def test_dhis2_connection():
    """Test connection to the public DHIS2 instance"""
    try:
        async with httpx.AsyncClient() as client:
            # Test basic authentication and API access
            response = await client.get(
                f"{TEST_DHIS2_BASE_URL}/api/system/info",
                auth=(TEST_DHIS2_USERNAME, TEST_DHIS2_PASSWORD),
                timeout=30.0
            )

            if response.status_code == 200:
                system_info = response.json()
                return {
                    "status": "connected",
                    "message": "Successfully connected to DHIS2 test instance",
                    "system_info": {
                        "version": system_info.get("version"),
                        "build_revision": system_info.get("buildRevision"),
                        "instance_base_url": system_info.get("instanceBaseUrl")
                    }
                }
            else:
                raise HTTPException(status_code=400, detail=f"Connection failed with status: {response.status_code}")

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Connection timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")

@router.get("/discovery-summary")
async def discovery_summary():
    """Get a summary of all available DHIS2 discovery endpoints"""
    return {
        "status": "success",
        "dhis2_instance": {
            "base_url": TEST_DHIS2_BASE_URL,
            "version": "2.42.2",
            "status": "connected"
        },
        "available_endpoints": {
            "connection_test": "/api/dhis2/test-connection",
            "analytics_test": "/api/dhis2/test-analytics",
            "discover_datasets": "/api/dhis2/discover/datasets?limit=10",
            "discover_data_elements": "/api/dhis2/discover/data-elements?limit=10&filter_text=malaria",
            "discover_org_units": "/api/dhis2/discover/organisation-units?level=2&limit=10",
            "discover_periods": "/api/dhis2/discover/periods",
            "fetch_analytics_data": "/api/dhis2/fetch-data?data_elements=FTRrcoaog83&periods=LAST_12_MONTHS&org_units=LEVEL-2"
        },
        "sample_data_elements": [
            {"id": "FTRrcoaog83", "name": "Accute Flaccid Paralysis (Deaths < 5 yrs)"},
            {"id": "YtbsuPPo010", "name": "Measles doses given"},
            {"id": "s46m5MS0hxu", "name": "BCG doses given"}
        ],
        "sample_org_units": [
            {"id": "O6uvpzGd5pu", "name": "Bo", "level": 2},
            {"id": "fdc6uOvgoji", "name": "Bombali", "level": 2},
            {"id": "lc3eMKXaEfw", "name": "Bonthe", "level": 2}
        ],
        "usage_examples": {
            "get_all_datasets": "GET /api/dhis2/discover/datasets?limit=50",
            "search_data_elements": "GET /api/dhis2/discover/data-elements?filter_text=vaccination&limit=20",
            "get_district_level_orgs": "GET /api/dhis2/discover/organisation-units?level=2",
            "fetch_vaccination_data": "GET /api/dhis2/fetch-data?data_elements=YtbsuPPo010,s46m5MS0hxu&periods=LAST_6_MONTHS&org_units=LEVEL-2"
        }
    }

@router.get("/test-analytics")
async def test_dhis2_analytics():
    """Test the specific analytics endpoint provided by the user"""
    try:
        async with httpx.AsyncClient() as client:
            # Test the specific analytics endpoint
            analytics_url = f"{TEST_DHIS2_BASE_URL}/api/analytics.json"
            params = {
                "dimension": ["dx:FTRrcoaog83", "pe:LAST_12_MONTHS", "ou:LEVEL-2"]
            }

            response = await client.get(
                analytics_url,
                params=params,
                auth=(TEST_DHIS2_USERNAME, TEST_DHIS2_PASSWORD),
                timeout=30.0
            )

            if response.status_code == 200:
                analytics_data = response.json()
                return {
                    "status": "success",
                    "message": "Successfully fetched analytics data",
                    "data_preview": {
                        "headers": analytics_data.get("headers", []),
                        "dimensions": analytics_data.get("metaData", {}).get("dimensions", {}),
                        "row_count": len(analytics_data.get("rows", [])),
                        "sample_rows": analytics_data.get("rows", [])[:5]  # First 5 rows as preview
                    }
                }
            else:
                raise HTTPException(status_code=400, detail=f"Analytics request failed with status: {response.status_code}")

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics request error: {str(e)}")

@router.post("/connections")
async def create_connection(db: Session = Depends(get_db)):
    return {"message": "Create DHIS2 connection endpoint"}

@router.get("/connections")
async def list_connections(db: Session = Depends(get_db)):
    return {"message": "List DHIS2 connections endpoint"}

@router.post("/sync/{connection_id}")
async def sync_data(connection_id: int, db: Session = Depends(get_db)):
    return {"message": f"Sync data from DHIS2 connection {connection_id}"}

@router.get("/discover/datasets")
async def discover_datasets(limit: int = 50):
    """Discover all available datasets from DHIS2 test instance"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TEST_DHIS2_BASE_URL}/api/dataSets",
                params={
                    "fields": "id,name,displayName,periodType,categoryCombo[name],dataSetElements[dataElement[id,name,displayName,valueType]]",
                    "paging": "false" if limit > 100 else "true",
                    "pageSize": min(limit, 100)
                },
                auth=(TEST_DHIS2_USERNAME, TEST_DHIS2_PASSWORD),
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                datasets = data.get("dataSets", [])

                return {
                    "status": "success",
                    "message": f"Found {len(datasets)} datasets",
                    "total_count": len(datasets),
                    "datasets": datasets[:limit]
                }
            else:
                raise HTTPException(status_code=400, detail=f"Failed to fetch datasets: {response.status_code}")

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching datasets: {str(e)}")

@router.get("/discover/data-elements")
async def discover_data_elements(limit: int = 50, filter_text: str = None):
    """Discover available data elements from DHIS2 test instance"""
    try:
        async with httpx.AsyncClient() as client:
            params = {
                "fields": "id,name,displayName,valueType,domainType,aggregationType,categoryCombo[name]",
                "paging": "false" if limit > 100 else "true",
                "pageSize": min(limit, 100)
            }

            if filter_text:
                params["filter"] = f"name:ilike:{filter_text}"

            response = await client.get(
                f"{TEST_DHIS2_BASE_URL}/api/dataElements",
                params=params,
                auth=(TEST_DHIS2_USERNAME, TEST_DHIS2_PASSWORD),
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                elements = data.get("dataElements", [])

                return {
                    "status": "success",
                    "message": f"Found {len(elements)} data elements",
                    "total_count": len(elements),
                    "data_elements": elements[:limit]
                }
            else:
                raise HTTPException(status_code=400, detail=f"Failed to fetch data elements: {response.status_code}")

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data elements: {str(e)}")

@router.get("/discover/organisation-units")
async def discover_organisation_units(level: int = None, limit: int = 50):
    """Discover organization units from DHIS2 test instance"""
    try:
        async with httpx.AsyncClient() as client:
            params = {
                "fields": "id,name,displayName,level,path,parent[id,name],children[id,name]",
                "paging": "false" if limit > 100 else "true",
                "pageSize": min(limit, 100)
            }

            if level:
                params["filter"] = f"level:eq:{level}"

            response = await client.get(
                f"{TEST_DHIS2_BASE_URL}/api/organisationUnits",
                params=params,
                auth=(TEST_DHIS2_USERNAME, TEST_DHIS2_PASSWORD),
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                org_units = data.get("organisationUnits", [])

                return {
                    "status": "success",
                    "message": f"Found {len(org_units)} organization units",
                    "total_count": len(org_units),
                    "organisation_units": org_units[:limit]
                }
            else:
                raise HTTPException(status_code=400, detail=f"Failed to fetch organization units: {response.status_code}")

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching organization units: {str(e)}")

@router.get("/discover/periods")
async def discover_periods(period_type: str = "Monthly", limit: int = 24):
    """Generate period information for DHIS2 analytics"""
    try:
        # Generate commonly used period options for DHIS2
        relative_periods = [
            "TODAY", "YESTERDAY", "LAST_3_DAYS", "LAST_7_DAYS", "LAST_14_DAYS",
            "THIS_WEEK", "LAST_WEEK", "LAST_4_WEEKS", "LAST_12_WEEKS", "LAST_52_WEEKS",
            "THIS_MONTH", "LAST_MONTH", "LAST_3_MONTHS", "LAST_6_MONTHS", "LAST_12_MONTHS",
            "THIS_BIMONTH", "LAST_BIMONTH", "LAST_6_BIMONTHS",
            "THIS_QUARTER", "LAST_QUARTER", "LAST_4_QUARTERS",
            "THIS_SIX_MONTH", "LAST_SIX_MONTH", "LAST_2_SIXMONTHS",
            "THIS_YEAR", "LAST_YEAR", "LAST_5_YEARS"
        ]

        # Generate some specific period IDs (e.g., for monthly periods)
        specific_periods = [
            {"id": "202410", "name": "October 2024", "displayName": "October 2024", "periodType": "Monthly"},
            {"id": "202411", "name": "November 2024", "displayName": "November 2024", "periodType": "Monthly"},
            {"id": "202412", "name": "December 2024", "displayName": "December 2024", "periodType": "Monthly"},
            {"id": "202501", "name": "January 2025", "displayName": "January 2025", "periodType": "Monthly"},
            {"id": "202502", "name": "February 2025", "displayName": "February 2025", "periodType": "Monthly"},
            {"id": "202503", "name": "March 2025", "displayName": "March 2025", "periodType": "Monthly"},
            {"id": "202504", "name": "April 2025", "displayName": "April 2025", "periodType": "Monthly"},
            {"id": "202505", "name": "May 2025", "displayName": "May 2025", "periodType": "Monthly"},
            {"id": "202506", "name": "June 2025", "displayName": "June 2025", "periodType": "Monthly"},
            {"id": "202507", "name": "July 2025", "displayName": "July 2025", "periodType": "Monthly"},
            {"id": "202508", "name": "August 2025", "displayName": "August 2025", "periodType": "Monthly"},
            {"id": "202509", "name": "September 2025", "displayName": "September 2025", "periodType": "Monthly"}
        ]

        return {
            "status": "success",
            "message": "Period options available for DHIS2 analytics",
            "relative_periods": relative_periods,
            "specific_periods": specific_periods[:limit],
            "usage_note": "Use relative periods (e.g., LAST_12_MONTHS) or specific period IDs (e.g., 202501) in analytics queries"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating periods: {str(e)}")

@router.get("/fetch-data")
async def fetch_comprehensive_data(
    data_elements: str = "FTRrcoaog83,fbfJHqxpdbK",  # Multiple data elements
    periods: str = "LAST_12_MONTHS",
    org_units: str = "LEVEL-2",
    include_metadata: bool = True
):
    """Fetch comprehensive analytics data with multiple dimensions"""
    try:
        async with httpx.AsyncClient() as client:
            # Parse comma-separated values
            dx_params = [f"dx:{de.strip()}" for de in data_elements.split(",") if de.strip()]

            params = {
                "dimension": dx_params + [f"pe:{periods}", f"ou:{org_units}"]
            }

            if include_metadata:
                params["includeMetadataDetails"] = "true"

            response = await client.get(
                f"{TEST_DHIS2_BASE_URL}/api/analytics.json",
                params=params,
                auth=(TEST_DHIS2_USERNAME, TEST_DHIS2_PASSWORD),
                timeout=30.0
            )

            if response.status_code == 200:
                analytics_data = response.json()

                # Process and structure the response
                result = {
                    "status": "success",
                    "message": "Analytics data fetched successfully",
                    "query_parameters": {
                        "data_elements": data_elements.split(","),
                        "periods": periods,
                        "organisation_units": org_units
                    },
                    "data": {
                        "headers": analytics_data.get("headers", []),
                        "rows": analytics_data.get("rows", []),
                        "row_count": len(analytics_data.get("rows", [])),
                        "metadata": analytics_data.get("metaData", {}) if include_metadata else None
                    }
                }

                return result
            else:
                raise HTTPException(status_code=400, detail=f"Analytics request failed: {response.status_code}")

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analytics data: {str(e)}")

@router.post("/datasets/sync")
async def sync_datasets_to_db(connection_id: int = 1, limit: int = 50, db: Session = Depends(get_db)):
    """Sync datasets from DHIS2 to local database"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TEST_DHIS2_BASE_URL}/api/dataSets",
                params={
                    "fields": "id,name,displayName,periodType,categoryCombo[name],dataSetElements[dataElement[id,name,displayName,valueType,domainType,aggregationType,categoryCombo[name]]]",
                    "paging": "false" if limit > 100 else "true",
                    "pageSize": min(limit, 100)
                },
                auth=(TEST_DHIS2_USERNAME, TEST_DHIS2_PASSWORD),
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                datasets = data.get("dataSets", [])

                synced_datasets = []
                for dataset_data in datasets:
                    # Check if dataset already exists
                    existing_dataset = db.query(Dataset).filter(Dataset.dhis2_id == dataset_data["id"]).first()

                    if not existing_dataset:
                        # Create new dataset
                        dataset = Dataset(
                            dhis2_id=dataset_data["id"],
                            name=dataset_data["name"],
                            display_name=dataset_data.get("displayName"),
                            period_type=dataset_data.get("periodType", "Unknown"),
                            category_combo=dataset_data.get("categoryCombo"),
                            connection_id=connection_id
                        )
                        db.add(dataset)
                        db.commit()
                        db.refresh(dataset)

                        # Add data elements
                        data_set_elements = dataset_data.get("dataSetElements", [])
                        for element_wrapper in data_set_elements:
                            element_data = element_wrapper.get("dataElement", {})
                            if element_data:
                                data_element = DataElement(
                                    dhis2_id=element_data["id"],
                                    name=element_data["name"],
                                    display_name=element_data.get("displayName"),
                                    value_type=element_data.get("valueType"),
                                    domain_type=element_data.get("domainType"),
                                    aggregation_type=element_data.get("aggregationType"),
                                    category_combo=element_data.get("categoryCombo"),
                                    dataset_id=dataset.id
                                )
                                db.add(data_element)

                        db.commit()
                        synced_datasets.append({
                            "id": dataset.id,
                            "dhis2_id": dataset.dhis2_id,
                            "name": dataset.name,
                            "period_type": dataset.period_type,
                            "data_elements_count": len(data_set_elements)
                        })

                return {
                    "status": "success",
                    "message": f"Synced {len(synced_datasets)} new datasets",
                    "synced_datasets": synced_datasets
                }
            else:
                raise HTTPException(status_code=400, detail=f"Failed to fetch datasets: {response.status_code}")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error syncing datasets: {str(e)}")

@router.get("/datasets")
async def get_stored_datasets(db: Session = Depends(get_db)):
    """Get all stored datasets from local database"""
    try:
        datasets = db.query(Dataset).all()

        result = []
        for dataset in datasets:
            data_elements_count = len(dataset.data_elements)
            result.append({
                "id": dataset.id,
                "dhis2_id": dataset.dhis2_id,
                "name": dataset.name,
                "display_name": dataset.display_name,
                "period_type": dataset.period_type,
                "category_combo": dataset.category_combo,
                "data_elements_count": data_elements_count,
                "created_at": dataset.created_at
            })

        return {
            "status": "success",
            "message": f"Found {len(result)} stored datasets",
            "datasets": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stored datasets: {str(e)}")

@router.get("/datasets/{dataset_id}/data-elements")
async def get_dataset_data_elements(dataset_id: int, db: Session = Depends(get_db)):
    """Get all data elements for a specific dataset"""
    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        data_elements = []
        for element in dataset.data_elements:
            data_elements.append({
                "id": element.id,
                "dhis2_id": element.dhis2_id,
                "name": element.name,
                "display_name": element.display_name,
                "value_type": element.value_type,
                "domain_type": element.domain_type,
                "aggregation_type": element.aggregation_type,
                "category_combo": element.category_combo
            })

        return {
            "status": "success",
            "dataset": {
                "id": dataset.id,
                "name": dataset.name,
                "display_name": dataset.display_name,
                "period_type": dataset.period_type
            },
            "data_elements": data_elements,
            "total_count": len(data_elements)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data elements: {str(e)}")

@router.get("/datasets/{dataset_id}/data")
async def fetch_dataset_data(
    dataset_id: int,
    periods: str = "LAST_12_MONTHS",
    org_units: str = "LEVEL-2",
    db: Session = Depends(get_db)
):
    """Fetch actual data values for a dataset from DHIS2"""
    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Get all data element IDs for this dataset
        data_element_ids = [element.dhis2_id for element in dataset.data_elements]

        if not data_element_ids:
            return {
                "status": "success",
                "message": "No data elements found for this dataset",
                "data": {"headers": [], "rows": [], "row_count": 0}
            }

        async with httpx.AsyncClient() as client:
            # Create dimension parameters for all data elements
            dx_params = [f"dx:{de_id}" for de_id in data_element_ids]

            params = {
                "dimension": dx_params + [f"pe:{periods}", f"ou:{org_units}"],
                "includeMetadataDetails": "true"
            }

            response = await client.get(
                f"{TEST_DHIS2_BASE_URL}/api/analytics.json",
                params=params,
                auth=(TEST_DHIS2_USERNAME, TEST_DHIS2_PASSWORD),
                timeout=30.0
            )

            if response.status_code == 200:
                analytics_data = response.json()

                return {
                    "status": "success",
                    "message": f"Data fetched for dataset: {dataset.name}",
                    "dataset": {
                        "id": dataset.id,
                        "name": dataset.name,
                        "period_type": dataset.period_type
                    },
                    "query_parameters": {
                        "data_elements": data_element_ids,
                        "periods": periods,
                        "org_units": org_units
                    },
                    "data": {
                        "headers": analytics_data.get("headers", []),
                        "rows": analytics_data.get("rows", []),
                        "row_count": len(analytics_data.get("rows", [])),
                        "metadata": analytics_data.get("metaData", {})
                    }
                }
            else:
                raise HTTPException(status_code=400, detail=f"DHIS2 analytics request failed: {response.status_code}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching dataset data: {str(e)}")

@router.get("/datasets/{connection_id}")
async def get_datasets(connection_id: int, db: Session = Depends(get_db)):
    return {"message": f"Get datasets from DHIS2 connection {connection_id}"}