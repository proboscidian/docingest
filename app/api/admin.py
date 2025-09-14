from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import os
from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger
from app.services.token_storage import TokenStorage
from datetime import datetime
from app.api.ingest import active_jobs

router = APIRouter()
logger = get_logger(__name__)
token_storage = TokenStorage()

# Security for admin operations
security = HTTPBearer()

def verify_admin_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin API key for authentication"""
    settings = get_settings()
    if credentials.credentials != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key"
        )
    return credentials.credentials

class ApiKeyData(BaseModel):
    id: str
    siteName: str
    siteUrl: str
    contactEmail: str
    planType: str
    notes: str
    apiKey: str
    createdAt: str
    status: str
    usage: Dict[str, Any]

class ApiKeysRequest(BaseModel):
    apiKeys: List[ApiKeyData]

@router.post("/save-api-keys")
async def save_api_keys(request: ApiKeysRequest, admin_key: str = Depends(verify_admin_key)):
    """Save API keys from admin panel"""
    try:
        # Convert to dict format for JSON storage
        api_keys_data = []
        for key_data in request.apiKeys:
            api_keys_data.append({
                "id": key_data.id,
                "siteName": key_data.siteName,
                "siteUrl": key_data.siteUrl,
                "contactEmail": key_data.contactEmail,
                "planType": key_data.planType,
                "notes": key_data.notes,
                "apiKey": key_data.apiKey,
                "createdAt": key_data.createdAt,
                "status": key_data.status,
                "usage": key_data.usage
            })
        
        # Save to file
        with open("api_keys.json", "w") as f:
            json.dump(api_keys_data, f, indent=2)
        
        logger.info(f"Saved {len(api_keys_data)} API keys to file")
        
        return {
            "success": True,
            "message": f"Saved {len(api_keys_data)} API keys",
            "count": len(api_keys_data)
        }
        
    except Exception as e:
        logger.error(f"Error saving API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save API keys"
        )

@router.get("/api-keys")
async def get_api_keys(admin_key: str = Depends(verify_admin_key)):
    """Get all API keys"""
    try:
        if os.path.exists("api_keys.json"):
            with open("api_keys.json", "r") as f:
                api_keys = json.load(f)
            return {
                "success": True,
                "apiKeys": api_keys,
                "count": len(api_keys)
            }
        else:
            return {
                "success": True,
                "apiKeys": [],
                "count": 0
            }
    except Exception as e:
        logger.error(f"Error reading API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read API keys"
        )

@router.get("/connections")
async def get_connections(admin_key: str = Depends(verify_admin_key)):
    """List connected sites and summary stats for the admin panel"""
    try:
        stats = token_storage.get_connection_stats()
        tenants = []
        for tenant, _count in stats.get('tenant_stats', {}).items():
            conns = token_storage.get_connections_for_tenant(tenant)
            # Normalize timestamps
            for c in conns:
                if isinstance(c.get('created_at'), (int, float)):
                    c['created_at_iso'] = datetime.utcfromtimestamp(c['created_at']).isoformat() + 'Z'
                if c.get('last_used_at') and isinstance(c.get('last_used_at'), (int, float)):
                    c['last_used_at_iso'] = datetime.utcfromtimestamp(c['last_used_at']).isoformat() + 'Z'
            tenants.append({
                'tenant': tenant,
                'connections': conns,
                'count': len(conns)
            })

        return {
            'success': True,
            'stats': stats,
            'tenants': tenants
        }
    except Exception as e:
        logger.error(f"Error retrieving connections: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve connections")

@router.get("/jobs")
async def list_jobs(tenant: str | None = None, admin_key: str = Depends(verify_admin_key)):
    """List active/known jobs for the admin panel (in-memory)."""
    try:
        jobs = []
        for job in active_jobs.values():
            job_dict = job.dict()
            if tenant and job_dict.get('tenant') != tenant:
                continue
            jobs.append(job_dict)
        return {"success": True, "count": len(jobs), "jobs": jobs}
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list jobs")
