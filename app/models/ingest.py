from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class GoogleCredentials(BaseModel):
    """Google OAuth credentials provided by tenant"""
    client_id: str = Field(..., description="Google OAuth client ID")
    client_secret: str = Field(..., description="Google OAuth client secret")
    refresh_token: str = Field(..., description="Google OAuth refresh token")

class DriveConfig(BaseModel):
    """Google Drive configuration"""
    folder_ids: List[str] = Field(..., description="List of Google Drive folder IDs to ingest")

class IngestRequest(BaseModel):
    """Request model for starting document ingestion"""
    tenant: str = Field(..., description="Tenant identifier")
    connection_id: str = Field(..., description="Google OAuth connection ID")
    drive: DriveConfig = Field(..., description="Google Drive configuration")
    reingest: str = Field(default="incremental", description="Reingest mode: incremental or full")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant": "extreme-coatings",
                "connection_id": "conn_abc123",
                "drive": {
                    "folder_ids": ["<FOLDER_ID_1>", "<FOLDER_ID_2>"]
                },
                "reingest": "incremental"
            }
        }

class IngestResponse(BaseModel):
    """Response model for ingest job creation"""
    success: bool = Field(..., description="Whether the job was created successfully")
    job_id: str = Field(..., description="Unique job identifier")
    message: str = Field(..., description="Status message")

class JobProgress(BaseModel):
    """Job progress information"""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current job status")
    started_at: datetime = Field(..., description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    processed_docs: int = Field(default=0, description="Number of documents processed")
    processed_pages: int = Field(default=0, description="Number of pages processed")
    total_docs: int = Field(default=0, description="Total documents to process")
    total_pages: int = Field(default=0, description="Total pages to process")
    errors: List[str] = Field(default=[], description="List of errors encountered")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_12345",
                "status": "running",
                "started_at": "2024-01-01T10:00:00Z",
                "processed_docs": 5,
                "processed_pages": 25,
                "total_docs": 10,
                "total_pages": 50,
                "errors": []
            }
        }

class QueryRequest(BaseModel):
    """Request model for semantic search"""
    tenant: str = Field(..., description="Tenant identifier")
    query: str = Field(..., description="Search query")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of results to return")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant": "example_company",
                "query": "What are the safety procedures?",
                "top_k": 10
            }
        }

class SearchHit(BaseModel):
    """Individual search result"""
    text: str = Field(..., description="Chunk text content")
    doc_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    page: int = Field(..., description="Page number")
    score: float = Field(..., description="Relevance score")
    drive_path: str = Field(..., description="Google Drive path")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Safety procedures must be followed at all times...",
                "doc_id": "doc_123",
                "title": "Safety Manual",
                "page": 5,
                "score": 0.95,
                "drive_path": "/Safety/Safety Manual.pdf"
            }
        }

class QueryResponse(BaseModel):
    """Response model for semantic search"""
    success: bool = Field(..., description="Whether the search was successful")
    hits: List[SearchHit] = Field(..., description="Search results")
    total_hits: int = Field(..., description="Total number of matching results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "hits": [
                    {
                        "text": "Safety procedures must be followed...",
                        "doc_id": "doc_123",
                        "title": "Safety Manual",
                        "page": 5,
                        "score": 0.95,
                        "drive_path": "/Safety/Safety Manual.pdf"
                    }
                ],
                "total_hits": 1
            }
        }

class CollectionInitRequest(BaseModel):
    """Request model for collection initialization"""
    tenant: str = Field(..., description="Tenant identifier")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant": "example_company"
            }
        }

class CollectionInitResponse(BaseModel):
    """Response model for collection initialization"""
    success: bool = Field(..., description="Whether the collection was created successfully")
    collection_name: str = Field(..., description="Name of the created collection")
    message: str = Field(..., description="Status message")
