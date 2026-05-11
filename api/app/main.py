from fastapi import FastAPI

from app.routers.files import router as files_router
from app.storage import ensure_bucket_exists


app = FastAPI(title="Cloud File Storage API")


@app.on_event("startup")
def startup_event():
    ensure_bucket_exists()


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


app.include_router(files_router)