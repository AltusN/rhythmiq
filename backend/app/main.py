from fastapi import FastAPI

from app.db import lifespan
from app.routers.club import router as club_router
from app.routers.coach import router as coach_router
from app.routers.district import router as district_router
from app.routers.gymnast import router as gymnast_router

app = FastAPI(
    title="Rhytmiq API",
    description="FIG-compliant API for managing rhythmic gymnastics meets",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(club_router)
app.include_router(district_router)
app.include_router(coach_router)
app.include_router(gymnast_router)

@app.get("/", tags=["/health"])
def root():
    return {"status": "ok", "service": "Rhytmiq API"}
