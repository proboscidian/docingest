from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
import os
from dotenv import load_dotenv
import json
from loguru import logger

from app.api import ingest, health, admin, oauth, search
from app.utils.config import get_settings
from app.utils.logging_optimized import setup_logging
from app.middleware.ip_whitelist import IPWhitelistMiddleware

# Load environment variables
load_dotenv()

# Initialize settings
settings = get_settings()

# Setup logging
setup_logging()

app = FastAPI(
    title="Document Ingest Service",
    description="Document processing and ingestion service for Google Drive documents",
    version="1.0.0",
    docs_url=None,  # Disable public docs
    redoc_url=None  # Disable public redoc
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["docingest.industrialwebworks.net", "localhost", "127.0.0.1"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Add IP whitelist middleware
app.add_middleware(IPWhitelistMiddleware)

# Security
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for authentication"""
    if credentials.credentials != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials

def verify_any_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin key or a valid active plugin key from api_keys.json"""
    provided_key = credentials.credentials
    # Admin key always allowed
    if provided_key == settings.api_secret_key:
        return provided_key
    # Check plugin keys file
    try:
        keys_path = "api_keys.json"
        if os.path.exists(keys_path):
            with open(keys_path, "r") as f:
                stored_keys = json.load(f)
            for key_data in stored_keys:
                if key_data.get("apiKey") == provided_key and key_data.get("status") == "active":
                    return provided_key
    except Exception:
        pass
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

# Include API routes
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])  # OAuth endpoints (no auth required for callback)
app.include_router(search.health_router, prefix="/search", tags=["search-health"])  # Search health (no auth)
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"], dependencies=[Depends(verify_any_key)])
app.include_router(search.router, prefix="/search", tags=["search"], dependencies=[Depends(verify_any_key)])
app.include_router(admin.router, prefix="/admin", tags=["admin"], dependencies=[Depends(verify_api_key)])

@app.get("/")
async def root():
    """Root endpoint - serve dashboard"""
    from fastapi.responses import FileResponse
    import os
    
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    else:
        return {
            "service": "Document Ingest Service",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "dashboard": "Dashboard not found - using fallback"
        }

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8999,
        log_level="info"
    )
