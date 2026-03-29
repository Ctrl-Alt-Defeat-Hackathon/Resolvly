from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings
from api.routes import health, upload, extract, analyze, outputs, wizard, codes, export

settings = get_settings()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)

# Mount routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(upload.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(extract.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(analyze.router, prefix="/api/v1/claims", tags=["Analysis"])
app.include_router(outputs.router, prefix="/api/v1/outputs", tags=["Outputs"])
app.include_router(wizard.router, prefix="/api/v1/wizard", tags=["Wizard"])
app.include_router(codes.router, prefix="/api/v1/codes", tags=["Codes"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
