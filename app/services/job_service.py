import redis
from typing import Dict, Optional
from datetime import datetime, timedelta
from app.models.ingest import JobProgress, JobStatus
from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger, log_error
from app.utils.security import generate_job_id

logger = get_logger(__name__)

class JobService:
    """Job management service"""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self._connect_redis()
    
    def _connect_redis(self):
        """Connect to Redis for job storage"""
        try:
            self.redis_client = redis.from_url(self.settings.redis_url)
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed, using in-memory storage: {e}")
            self.redis_client = None
    
    def create_job(self, tenant: str, job_type: str = "ingest") -> str:
        """Create a new job"""
        job_id = generate_job_id()
        
        job_data = {
            "job_id": job_id,
            "tenant": tenant,
            "job_type": job_type,
            "status": JobStatus.QUEUED,
            "started_at": datetime.utcnow().isoformat(),
            "processed_docs": 0,
            "processed_pages": 0,
            "total_docs": 0,
            "total_pages": 0,
            "errors": []
        }
        
        if self.redis_client:
            # Store in Redis with expiration
            self.redis_client.setex(
                f"job:{job_id}",
                timedelta(hours=24),
                str(job_data)
            )
        else:
            # Store in memory (fallback)
            if not hasattr(self, '_memory_jobs'):
                self._memory_jobs = {}
            self._memory_jobs[job_id] = job_data
        
        logger.info(f"Created job {job_id} for tenant {tenant}")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[JobProgress]:
        """Get job progress"""
        try:
            if self.redis_client:
                job_data = self.redis_client.get(f"job:{job_id}")
                if job_data:
                    job_dict = eval(job_data)  # In production, use proper JSON parsing
                    return self._dict_to_job_progress(job_dict)
            else:
                # Memory fallback
                if hasattr(self, '_memory_jobs') and job_id in self._memory_jobs:
                    return self._dict_to_job_progress(self._memory_jobs[job_id])
            
            return None
            
        except Exception as e:
            log_error(e, f"Error getting job {job_id}")
            return None
    
    def update_job_progress(self, job_id: str, **kwargs) -> bool:
        """Update job progress"""
        try:
            job = self.get_job(job_id)
            if not job:
                return False
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            
            # Convert back to dict
            job_dict = self._job_progress_to_dict(job)
            
            if self.redis_client:
                self.redis_client.setex(
                    f"job:{job_id}",
                    timedelta(hours=24),
                    str(job_dict)
                )
            else:
                # Memory fallback
                if hasattr(self, '_memory_jobs'):
                    self._memory_jobs[job_id] = job_dict
            
            return True
            
        except Exception as e:
            log_error(e, f"Error updating job {job_id}")
            return False
    
    def complete_job(self, job_id: str, success: bool = True, error_message: str = None) -> bool:
        """Mark job as completed or failed"""
        try:
            update_data = {
                "status": JobStatus.COMPLETED if success else JobStatus.FAILED,
                "completed_at": datetime.utcnow().isoformat()
            }
            
            if error_message:
                job = self.get_job(job_id)
                if job:
                    job.errors.append(error_message)
                    update_data["errors"] = job.errors
            
            return self.update_job_progress(job_id, **update_data)
            
        except Exception as e:
            log_error(e, f"Error completing job {job_id}")
            return False
    
    def _dict_to_job_progress(self, job_dict: Dict) -> JobProgress:
        """Convert dictionary to JobProgress object"""
        return JobProgress(
            job_id=job_dict["job_id"],
            status=JobStatus(job_dict["status"]),
            started_at=datetime.fromisoformat(job_dict["started_at"]),
            completed_at=datetime.fromisoformat(job_dict["completed_at"]) if job_dict.get("completed_at") else None,
            processed_docs=job_dict["processed_docs"],
            processed_pages=job_dict["processed_pages"],
            total_docs=job_dict["total_docs"],
            total_pages=job_dict["total_pages"],
            errors=job_dict["errors"]
        )
    
    def _job_progress_to_dict(self, job: JobProgress) -> Dict:
        """Convert JobProgress object to dictionary"""
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "started_at": job.started_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "processed_docs": job.processed_docs,
            "processed_pages": job.processed_pages,
            "total_docs": job.total_docs,
            "total_pages": job.total_pages,
            "errors": job.errors
        }
