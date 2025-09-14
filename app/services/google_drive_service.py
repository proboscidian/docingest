"""
Google Drive Service - Handles Google Drive API operations
Updated for centralized OAuth with connection-based access
"""

import httpx
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import hashlib

from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger
from app.services.google_oauth_service import GoogleOAuthService
from app.services.token_storage import TokenStorage

logger = get_logger(__name__)

class GoogleDriveService:
    """Google Drive API service using centralized OAuth connections"""
    
    def __init__(self):
        self.settings = get_settings()
        self.oauth_service = GoogleOAuthService()
        self.token_storage = TokenStorage()
        
        # Google Drive API endpoints
        self.drive_api_base = "https://www.googleapis.com/drive/v3"
        self.files_endpoint = f"{self.drive_api_base}/files"
        self.about_endpoint = f"{self.drive_api_base}/about"
    
    async def get_connection_access_token(self, connection_id: str) -> Optional[str]:
        """Get valid access token for a connection"""
        return await self.oauth_service.get_valid_access_token(connection_id)
    
    async def test_connection(self, connection_id: str) -> Dict:
        """Test if a Google Drive connection is working"""
        try:
            access_token = await self.get_connection_access_token(connection_id)
            if not access_token:
                return {
                    'valid': False,
                    'error': 'No valid access token available'
                }
            
            # Test with Drive About API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.about_endpoint,
                    headers={'Authorization': f'Bearer {access_token}'},
                    params={'fields': 'user,storageQuota'}
                )
                
                if response.status_code == 200:
                    about_data = response.json()
                    return {
                        'valid': True,
                        'user': about_data.get('user', {}),
                        'storage': about_data.get('storageQuota', {})
                    }
                else:
                    return {
                        'valid': False,
                        'error': f'Drive API error: {response.status_code}'
                    }
                    
        except Exception as e:
            logger.error(f"Failed to test connection {connection_id}: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    async def list_drive_folders(self, connection_id: str, folder_id: str = None) -> List[Dict]:
        """List folders in Google Drive"""
        try:
            access_token = await self.get_connection_access_token(connection_id)
            if not access_token:
                logger.error(f"No access token for connection {connection_id}")
                return []
            
            # Default to root folder if no folder_id provided
            if not folder_id:
                folder_id = 'root'
            
            async with httpx.AsyncClient() as client:
                params = {
                    'q': f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    'fields': 'files(id,name,createdTime,modifiedTime,webViewLink)',
                    'orderBy': 'name'
                }
                
                response = await client.get(
                    self.files_endpoint,
                    headers={'Authorization': f'Bearer {access_token}'},
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    folders = []
                    for folder in data.get('files', []):
                        folders.append({
                            'id': folder['id'],
                            'name': folder['name'],
                            'created_time': folder.get('createdTime'),
                            'modified_time': folder.get('modifiedTime'),
                            'web_view_link': folder.get('webViewLink')
                        })
                    return folders
                else:
                    logger.error(f"Failed to list folders: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []
    
    async def list_drive_files(self, connection_id: str, folder_id: str = None, 
                             file_types: List[str] = None) -> List[Dict]:
        """List files in Google Drive folder"""
        try:
            access_token = await self.get_connection_access_token(connection_id)
            if not access_token:
                logger.error(f"No access token for connection {connection_id}")
                return []
            
            # Default to root folder if no folder_id provided
            if not folder_id:
                folder_id = 'root'
            
            # Build query for file types
            mime_types = [
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.google-apps.document',
                'text/plain'
            ]
            
            if file_types:
                mime_types = file_types
            
            mime_query = " or ".join([f"mimeType='{mime}'" for mime in mime_types])
            query = f"'{folder_id}' in parents and ({mime_query}) and trashed=false"
            
            async with httpx.AsyncClient() as client:
                params = {
                    'q': query,
                    'fields': 'files(id,name,mimeType,size,createdTime,modifiedTime,webViewLink,md5Checksum)',
                    'orderBy': 'modifiedTime desc'
                }
                
                response = await client.get(
                    self.files_endpoint,
                    headers={'Authorization': f'Bearer {access_token}'},
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    files = []
                    for file in data.get('files', []):
                        files.append({
                            'id': file['id'],
                            'name': file['name'],
                            'mime_type': file['mimeType'],
                            'size': file.get('size'),
                            'created_time': file.get('createdTime'),
                            'modified_time': file.get('modifiedTime'),
                            'web_view_link': file.get('webViewLink'),
                            'md5_checksum': file.get('md5Checksum')
                        })
                    return files
                else:
                    logger.error(f"Failed to list files: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []
    
    async def download_file(self, connection_id: str, file_id: str) -> Tuple[bytes, str]:
        """Download file content from Google Drive"""
        try:
            access_token = await self.get_connection_access_token(connection_id)
            if not access_token:
                raise Exception(f"No access token for connection {connection_id}")
            
            # First get file metadata
            async with httpx.AsyncClient() as client:
                metadata_response = await client.get(
                    f"{self.files_endpoint}/{file_id}",
                    headers={'Authorization': f'Bearer {access_token}'},
                    params={'fields': 'name,mimeType,size'}
                )
                
                if metadata_response.status_code != 200:
                    raise Exception(f"Failed to get file metadata: {metadata_response.status_code}")
                
                metadata = metadata_response.json()
                filename = metadata['name']
                mime_type = metadata['mimeType']
                
                # Handle Google Docs files (need to export)
                if mime_type.startswith('application/vnd.google-apps'):
                    export_mime_type = self._get_export_mime_type(mime_type)
                    download_url = f"{self.files_endpoint}/{file_id}/export"
                    params = {'mimeType': export_mime_type}
                else:
                    download_url = f"{self.files_endpoint}/{file_id}"
                    params = {'alt': 'media'}
                
                # Download file content
                download_response = await client.get(
                    download_url,
                    headers={'Authorization': f'Bearer {access_token}'},
                    params=params
                )
                
                if download_response.status_code == 200:
                    content = download_response.content
                    logger.info(f"Downloaded file {filename} ({len(content)} bytes)")
                    return content, filename
                else:
                    raise Exception(f"Failed to download file: {download_response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            raise
    
    def _get_export_mime_type(self, google_docs_mime_type: str) -> str:
        """Get export MIME type for Google Docs files"""
        export_types = {
            'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }
        return export_types.get(google_docs_mime_type, 'application/pdf')
    
    def get_file_sha256(self, content: bytes) -> str:
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(content).hexdigest()
    
    async def get_folder_hierarchy(self, connection_id: str, folder_id: str = None) -> Dict:
        """Get folder hierarchy for navigation"""
        try:
            access_token = await self.get_connection_access_token(connection_id)
            if not access_token:
                return {}
            
            if not folder_id:
                folder_id = 'root'
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.files_endpoint}/{folder_id}",
                    headers={'Authorization': f'Bearer {access_token}'},
                    params={'fields': 'id,name,parents'}
                )
                
                if response.status_code == 200:
                    folder_data = response.json()
                    hierarchy = {
                        'id': folder_data['id'],
                        'name': folder_data['name'],
                        'parents': folder_data.get('parents', [])
                    }
                    return hierarchy
                else:
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting folder hierarchy: {e}")
            return {}
    
    async def search_files(self, connection_id: str, query: str, 
                          folder_id: str = None) -> List[Dict]:
        """Search for files in Google Drive"""
        try:
            access_token = await self.get_connection_access_token(connection_id)
            if not access_token:
                return []
            
            search_query = f"name contains '{query}' and trashed=false"
            if folder_id:
                search_query += f" and '{folder_id}' in parents"
            
            async with httpx.AsyncClient() as client:
                params = {
                    'q': search_query,
                    'fields': 'files(id,name,mimeType,size,createdTime,modifiedTime,webViewLink)',
                    'orderBy': 'modifiedTime desc'
                }
                
                response = await client.get(
                    self.files_endpoint,
                    headers={'Authorization': f'Bearer {access_token}'},
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    files = []
                    for file in data.get('files', []):
                        files.append({
                            'id': file['id'],
                            'name': file['name'],
                            'mime_type': file['mimeType'],
                            'size': file.get('size'),
                            'created_time': file.get('createdTime'),
                            'modified_time': file.get('modifiedTime'),
                            'web_view_link': file.get('webViewLink')
                        })
                    return files
                else:
                    logger.error(f"Failed to search files: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return []
