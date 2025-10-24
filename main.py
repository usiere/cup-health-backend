from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db, engine, Base
import uvicorn

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Cuplime Health Data Intelligence API",
    description="Backend API for health data intelligence platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://localhost:5178",
        "http://localhost:5179",
        "http://localhost:5180",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
        "http://127.0.0.1:5179",
        "http://127.0.0.1:5180"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

@app.get("/")
async def root():
    return {"message": "Cuplime Health Data Intelligence API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include routers
from routers import auth, dhis2, queries, insights

# Import NLG models to ensure they're created
from models import nlg_optimized

app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(dhis2.router, prefix="/api/dhis2", tags=["dhis2"])
app.include_router(queries.router, prefix="/api/queries", tags=["queries"])
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)