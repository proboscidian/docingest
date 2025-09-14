from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import json
import os
from typing import List
from app.utils.logging_optimized import get_logger

logger = get_logger(__name__)

class IPWhitelistMiddleware:
    """IP Whitelist middleware to restrict access to authorized IPs only"""
    
    def __init__(self, app):
        self.app = app
        self.whitelist_file = "ip-whitelist.json"
        self.authorized_ips = self.load_authorized_ips()
    
    def load_authorized_ips(self) -> List[str]:
        """Load authorized IPs from JSON file"""
        try:
            if os.path.exists(self.whitelist_file):
                with open(self.whitelist_file, 'r') as f:
                    ip_data = json.load(f)
                    authorized_ips = ip_data.get('authorized_ips', [])
                    logger.info(f"Loaded {len(authorized_ips)} authorized IPs from whitelist")
                    return authorized_ips
            else:
                logger.warning(f"IP whitelist file {self.whitelist_file} not found")
                return []
        except Exception as e:
            logger.error(f"Error loading IP whitelist: {e}")
            return []
    
    def get_client_ip(self, request: Request) -> str:
        """Get the real client IP address"""
        # Check for forwarded headers first (from proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct connection IP
        return request.client.host
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        client_ip = self.get_client_ip(request)
        
        # Allow health check endpoint for monitoring
        if request.url.path.startswith("/health/"):
            await self.app(scope, receive, send)
            return
        
        # Check if IP is authorized
        if client_ip not in self.authorized_ips:
            logger.warning(f"Unauthorized IP access attempt: {client_ip} to {request.url.path}")
            
            response = JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access Denied",
                    "message": "Your IP address is not authorized to access this service",
                    "ip": client_ip
                }
            )
            await response(scope, receive, send)
            return
        
        logger.debug(f"Authorized IP access: {client_ip} to {request.url.path}")
        await self.app(scope, receive, send)
