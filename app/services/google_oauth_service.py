"""
Google OAuth Service - Handles Google OAuth flow and token management
"""

import secrets
import json
import base64
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import httpx
from urllib.parse import urlencode, parse_qs, urlparse

from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger
from app.services.token_storage import TokenStorage

logger = get_logger(__name__)

class GoogleOAuthService:
    """Handles Google OAuth flow and token management"""
    
    def __init__(self):
        self.settings = get_settings()
        self.token_storage = TokenStorage()
        
        # Google OAuth endpoints
        self.auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.revoke_url = "https://oauth2.googleapis.com/revoke"
        
        # Required scopes
        self.scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/userinfo.email"
        ]
    
    def generate_oauth_url(self, tenant: str, site_id: str, return_url: str, 
                          login_hint: Optional[str] = None) -> Tuple[str, str]:
        """Generate Google OAuth URL with secure state parameter"""
        try:
            # Generate secure state parameter
            nonce = secrets.token_urlsafe(32)
            state_data = {
                'tenant': tenant,
                'site_id': site_id,
                'return_url': return_url,
                'nonce': nonce,
                'timestamp': int(datetime.now().timestamp())
            }
            
            # Create signed state
            state_json = json.dumps(state_data)
            state_b64 = base64.urlsafe_b64encode(state_json.encode()).decode()
            
            # Sign the state with HMAC
            state_signature = hmac.new(
                self.settings.jwt_secret_key.encode(),
                state_b64.encode(),
                hashlib.sha256
            ).hexdigest()
            
            state = f"{state_b64}.{state_signature}"
            
            # Store state in database for validation
            self.token_storage.store_oauth_state(state, tenant, site_id, return_url, nonce)
            
            # Build OAuth URL
            params = {
                'client_id': self.settings.google_client_id,
                'redirect_uri': self.settings.google_redirect_uri,
                'response_type': 'code',
                'scope': ' '.join(self.scopes),
                'access_type': 'offline',
                'prompt': 'consent select_account',
                'include_granted_scopes': 'true',
                'state': state
            }
            
            if login_hint:
                params['login_hint'] = login_hint
            
            oauth_url = f"{self.auth_url}?{urlencode(params)}"
            
            logger.info(f"Generated OAuth URL for tenant {tenant}")
            return oauth_url, state
            
        except Exception as e:
            logger.error(f"Failed to generate OAuth URL: {e}")
            raise
    
    def validate_state(self, state: str) -> Optional[Dict]:
        """Validate OAuth state parameter"""
        try:
            if not state or '.' not in state:
                return None
            
            state_b64, signature = state.split('.', 1)
            
            # Verify signature
            expected_signature = hmac.new(
                self.settings.jwt_secret_key.encode(),
                state_b64.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("Invalid OAuth state signature")
                return None
            
            # Decode state data
            state_json = base64.urlsafe_b64decode(state_b64.encode()).decode()
            state_data = json.loads(state_json)
            
            # Check timestamp (state should be less than 10 minutes old)
            if datetime.now().timestamp() - state_data['timestamp'] > 600:
                logger.warning("OAuth state has expired")
                return None
            
            # Get from database for additional validation
            db_state = self.token_storage.get_oauth_state(state)
            if not db_state:
                logger.warning("OAuth state not found in database")
                return None
            
            return db_state
            
        except Exception as e:
            logger.error(f"Failed to validate OAuth state: {e}")
            return None
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Optional[Dict]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            # Validate state first
            state_data = self.validate_state(state)
            if not state_data:
                logger.error("Invalid OAuth state")
                return None
            
            # Exchange code for tokens
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data={
                    'client_id': self.settings.google_client_id,
                    'client_secret': self.settings.google_client_secret,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': self.settings.google_redirect_uri
                })
                
                if response.status_code != 200:
                    logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                    return None
                
                token_data = response.json()
            
            # Get user info
            user_info = await self.get_user_info(token_data['access_token'])
            
            # Generate connection ID
            connection_id = f"conn_{secrets.token_urlsafe(16)}"
            
            # Store connection
            success = self.token_storage.store_connection(
                connection_id=connection_id,
                tenant=state_data['tenant'],
                site_id=state_data['site_id'],
                user_email=user_info.get('email', ''),
                refresh_token=token_data['refresh_token'],
                access_token=token_data['access_token'],
                expires_in=token_data.get('expires_in', 3600)
            )
            
            if not success:
                logger.error("Failed to store connection")
                return None
            
            logger.info(f"Successfully created connection {connection_id} for tenant {state_data['tenant']}")
            
            return {
                'connection_id': connection_id,
                'tenant': state_data['tenant'],
                'site_id': state_data['site_id'],
                'user_email': user_info.get('email', ''),
                'return_url': state_data['return_url']
            }
            
        except Exception as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            return None
    
    async def get_user_info(self, access_token: str) -> Dict:
        """Get user information from Google"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get user info: {response.status_code}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return {}
    
    async def refresh_access_token(self, connection_id: str) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            connection = self.token_storage.get_connection(connection_id)
            if not connection:
                logger.error(f"Connection {connection_id} not found")
                return None
            
            refresh_token = connection['refresh_token']
            if not refresh_token:
                logger.error(f"No refresh token for connection {connection_id}")
                return None
            
            # Request new access token
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data={
                    'client_id': self.settings.google_client_id,
                    'client_secret': self.settings.google_client_secret,
                    'refresh_token': refresh_token,
                    'grant_type': 'refresh_token'
                })
                
                if response.status_code != 200:
                    logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                    return None
                
                token_data = response.json()
            
            # Update stored access token
            self.token_storage.update_access_token(
                connection_id, 
                token_data['access_token'], 
                token_data.get('expires_in', 3600)
            )
            
            logger.info(f"Refreshed access token for connection {connection_id}")
            return token_data['access_token']
            
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            return None
    
    async def get_valid_access_token(self, connection_id: str) -> Optional[str]:
        """Get valid access token, refreshing if necessary"""
        try:
            connection = self.token_storage.get_connection(connection_id)
            if not connection:
                return None
            
            # Check if access token is still valid
            if connection['expires_at'] and datetime.now().timestamp() < connection['expires_at']:
                return connection['access_token']
            
            # Token expired, refresh it
            return await self.refresh_access_token(connection_id)
            
        except Exception as e:
            logger.error(f"Failed to get valid access token: {e}")
            return None
    
    async def revoke_token(self, connection_id: str) -> bool:
        """Revoke Google OAuth tokens"""
        try:
            connection = self.token_storage.get_connection(connection_id)
            if not connection:
                return False
            
            refresh_token = connection['refresh_token']
            
            # Revoke token with Google
            async with httpx.AsyncClient() as client:
                response = await client.post(self.revoke_url, data={
                    'token': refresh_token
                })
                
                if response.status_code != 200:
                    logger.warning(f"Token revocation failed: {response.status_code}")
            
            # Mark connection as revoked in database
            self.token_storage.revoke_connection(connection_id)
            
            logger.info(f"Revoked tokens for connection {connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False
    
    def cleanup_expired_states(self):
        """Clean up expired OAuth states"""
        self.token_storage.cleanup_expired_states()
