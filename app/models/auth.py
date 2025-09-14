from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class AuthRequest(BaseModel):
    """Request model for authentication"""
    api_key: str = Field(..., description="API key for authentication")
    
class AuthResponse(BaseModel):
    """Response model for authentication"""
    success: bool = Field(..., description="Whether authentication was successful")
    message: str = Field(..., description="Authentication message")
    expires_at: Optional[str] = Field(None, description="Token expiration time")

class HealthCheck(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(..., description="Service version")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")

class DetailedHealthCheck(HealthCheck):
    """Detailed health check response model"""
    qdrant_status: str = Field(..., description="Qdrant connection status")
    drive_status: str = Field(..., description="Google Drive API status")
    embedding_model_status: str = Field(..., description="Embedding model status")
    memory_usage: Optional[Dict[str, Any]] = Field(None, description="Memory usage statistics")
    disk_usage: Optional[Dict[str, Any]] = Field(None, description="Disk usage statistics")
