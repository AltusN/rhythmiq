from fastapi import FastAPI

from app.db import lifespan
from backend.app.routers import district

app = FastAPI(
    title="Rhytmiq API",
    description="FIG-compliant API for managing rhythmic gymnastics meets",
    version="0.1.0",
)

@app.get("/", tags=["/health"])
def root():
    return {"status":"ok", "service": "Rhytmiq API"}