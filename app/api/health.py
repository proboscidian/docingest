from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
import psutil
import os
import json
from app.models.auth import HealthCheck, DetailedHealthCheck
from app.services.qdrant_service import QdrantService
from app.services.embedding_service_optimized import EmbeddingService
from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Track service start time
start_time = datetime.utcnow()

# Security for API key validation
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for authentication"""
    settings = get_settings()
    if credentials.credentials != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials

@router.get("/", response_model=HealthCheck)
async def health_check():
    """Basic health check"""
    uptime = (datetime.utcnow() - start_time).total_seconds()
    
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=get_settings().app_version,
        uptime=uptime
    )

@router.get("/detailed", response_model=DetailedHealthCheck)
async def detailed_health_check():
    """Detailed health check with system status"""
    uptime = (datetime.utcnow() - start_time).total_seconds()
    
    # Check Qdrant connection
    try:
        qdrant_service = QdrantService()
        qdrant_status = "healthy" if qdrant_service.is_connected() else "unhealthy"
    except Exception:
        qdrant_status = "unhealthy"
    
    # Check embedding model
    try:
        embedding_service = EmbeddingService()
        embedding_status = "healthy" if embedding_service.model is not None else "unhealthy"
    except Exception:
        embedding_status = "unhealthy"
    
    # Check Google Drive API (simplified)
    drive_status = "unknown"  # Would need actual API call to check
    
    # Get system metrics
    memory_info = psutil.virtual_memory()
    disk_info = psutil.disk_usage('/')
    
    memory_usage = {
        "total": memory_info.total,
        "available": memory_info.available,
        "percent": memory_info.percent,
        "used": memory_info.used
    }
    
    disk_usage = {
        "total": disk_info.total,
        "used": disk_info.used,
        "free": disk_info.free,
        "percent": (disk_info.used / disk_info.total) * 100
    }
    
    return DetailedHealthCheck(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=get_settings().app_version,
        uptime=uptime,
        qdrant_status=qdrant_status,
        drive_status=drive_status,
        embedding_model_status=embedding_status,
        memory_usage=memory_usage,
        disk_usage=disk_usage
    )

@router.get("/version")
async def get_version():
    """Get service version information"""
    return {
        "service": "Document Ingest Service",
        "version": get_settings().app_version,
        "build_time": start_time.isoformat(),
        "python_version": os.sys.version
    }

@router.get("/validate-key")
async def validate_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate API key and return status"""
    # In a real implementation, you'd check against a database
    # For now, we'll use a simple file-based approach
    
    try:
        # Get the API key from credentials
        api_key = credentials.credentials
        
        # Check if API key is in the stored keys (from admin panel)
        api_keys_file = "api_keys.json"
        logger.info(f"Validating API key: {api_key[:10]}...")
        logger.info(f"Looking for API keys file at: {api_keys_file}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        if os.path.exists(api_keys_file):
            logger.info(f"Found API keys file: {api_keys_file}")
            with open(api_keys_file, 'r') as f:
                stored_keys = json.load(f)
            
            logger.info(f"Loaded {len(stored_keys)} stored keys")
            
            # Find the key in stored keys
            for key_data in stored_keys:
                stored_key = key_data.get('apiKey', '')
                logger.info(f"Checking stored key: {stored_key[:10]}...")
                if stored_key == api_key:
                    logger.info(f"Found matching key for site: {key_data.get('siteName')}")
                    return {
                        "valid": True,
                        "active": key_data.get('status') == 'active',
                        "site_name": key_data.get('siteName'),
                        "site_url": key_data.get('siteUrl'),
                        "plan_type": key_data.get('planType'),
                        "created_at": key_data.get('createdAt'),
                        "message": "API key is valid and active" if key_data.get('status') == 'active' else "API key is valid but disabled"
                    }
        else:
            logger.info(f"API keys file not found: {api_keys_file}")
        
        # If not found in stored keys, check against main API key
        settings = get_settings()
        if api_key == settings.api_secret_key:
            return {
                "valid": True,
                "active": True,
                "site_name": "Default Service Key",
                "site_url": "https://docingest.industrialwebworks.net",
                "plan_type": "admin",
                "created_at": "2024-01-01T00:00:00Z",
                "message": "API key is valid and active"
            }
        
        # Key not found
        return {
            "valid": False,
            "active": False,
            "message": "API key not found or invalid"
        }
        
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        return {
            "valid": False,
            "active": False,
            "message": "Error validating API key"
        }
