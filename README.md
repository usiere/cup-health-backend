# Cuplime Backend

FastAPI backend for the Cuplime Health Data Intelligence Platform.

## Features
- RESTful API for health data management
- DHIS2 integration and data synchronization
- Natural language to SQL query conversion using OpenAI
- User authentication with JWT
- PostgreSQL database with SQLAlchemy ORM

## Tech Stack
- FastAPI for API framework
- PostgreSQL for database
- SQLAlchemy for ORM
- Alembic for database migrations
- OpenAI API for natural language processing
- JWT for authentication

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start development server
uvicorn main:app --reload
```

## Project Structure
```
backend/
├── models/          # SQLAlchemy database models
├── routers/         # FastAPI route handlers
├── services/        # Business logic services
├── schemas/         # Pydantic schemas
├── alembic/         # Database migration files
├── main.py          # FastAPI application entry point
└── database.py      # Database configuration
```

## API Endpoints
- `/api/auth/*` - Authentication endpoints
- `/api/dhis2/*` - DHIS2 connection and sync endpoints
- `/api/queries/*` - Natural language query endpoints
- `/api/insights/*` - Saved insights endpoints