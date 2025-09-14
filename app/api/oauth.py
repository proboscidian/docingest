"""
OAuth API Router - Handles Google OAuth flow endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from typing import Optional
from urllib.parse import urlencode, urlparse

from app.services.google_oauth_service import GoogleOAuthService
from app.services.google_drive_service import GoogleDriveService
from app.utils.logging_optimized import get_logger
from app.utils.config import get_settings

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

# Initialize services
oauth_service = GoogleOAuthService()
drive_service = GoogleDriveService()
# URL builder for plugin compatibility
@router.get("/url")
async def oauth_url(
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (plugin naming)"),
    redirect_uri: str = Query(..., description="WordPress return URL after OAuth completes at Docingest"),
    state: Optional[str] = Query(None, description="Opaque state from plugin for CSRF")
):
    """Return Google OAuth URL. Plugin-friendly GET endpoint.
    Externally exposed at /ingestapp/oauth/url
    """
    try:
        # Derive tenant/site_id
        parsed = urlparse(redirect_uri)
        host = parsed.netloc.lower()
        derived_site_id = host
        first_label = host.split(':')[0].split('.')[0] if host else 'site'
        derived_tenant = (tenant_id or first_label or 'site').replace('-', '_')

        # Generate OAuth URL; if state provided, pass through as login_hint extension via service state
        oauth_url, generated_state = oauth_service.generate_oauth_url(
            tenant=derived_tenant,
            site_id=derived_site_id,
            return_url=redirect_uri,
            login_hint=None
        )

        return {
            "oauth_url": oauth_url,
            "state": generated_state
        }
    except Exception as e:
        logger.error(f"Failed to generate OAuth URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate OAuth URL")

@router.get("/start")
async def start_oauth(
    tenant: str = Query(..., description="Tenant identifier"),
    site_id: str = Query(..., description="Site identifier"),
    return_url: str = Query(..., description="URL to return to after OAuth"),
    login_hint: Optional[str] = Query(None, description="Email hint for Google login")
):
    """Start Google OAuth flow"""
    try:
        logger.info(f"Starting OAuth flow for tenant {tenant}, site {site_id}")
        
        # Generate OAuth URL
        oauth_url, state = oauth_service.generate_oauth_url(
            tenant=tenant,
            site_id=site_id,
            return_url=return_url,
            login_hint=login_hint
        )
        
        # Redirect to Google OAuth
        return RedirectResponse(url=oauth_url)
        
    except Exception as e:
        logger.error(f"Failed to start OAuth flow: {e}")
        raise HTTPException(status_code=500, detail="Failed to start OAuth flow")

@router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for validation"),
    error: Optional[str] = Query(None, description="Error from Google OAuth")
):
    """Handle Google OAuth callback"""
    try:
        # Check for OAuth errors
        if error:
            logger.error(f"OAuth error: {error}")
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
        
        logger.info(f"Processing OAuth callback with code: {code[:10]}...")
        
        # Exchange code for tokens (should work whether first-time or already-approved)
        result = await oauth_service.exchange_code_for_tokens(code, state)
        
        if not result:
            raise HTTPException(status_code=400, detail="Failed to exchange code for tokens")
        
        # Redirect back to WordPress with success
        return_url = result['return_url']
        success_params = {
            'ok': '1',
            'connection_id': result['connection_id'],
            'tenant': result['tenant'],
            'user_email': result['user_email'],
            'state': result.get('state') or state
        }
        
        redirect_url = f"{return_url}?{urlencode(success_params)}"
        logger.info(f"OAuth successful, sending auto-close popup script to: {return_url}")

        # If opened in a popup, notify opener and close; otherwise, hard redirect
        html = f"""
        <html>
          <head><title>Connecting…</title></head>
          <body>
            <script>
              (function() {{
                var redirectUrl = {redirect_url!r};
                try {{
                  if (window.opener && !window.opener.closed) {{
                    window.opener.location = redirectUrl;
                    window.close();
                  }} else {{
                    window.location = redirectUrl;
                  }}
                }} catch (e) {{
                  window.location = redirectUrl;
                }}
              }})();
            </script>
            <noscript>
              <meta http-equiv="refresh" content="0;url={redirect_url}" />
              <p>Redirecting… If you are not redirected, <a href="{redirect_url}">click here</a>.</p>
            </noscript>
          </body>
        </html>
        """
        return HTMLResponse(content=html)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process OAuth callback: {e}")
        raise HTTPException(status_code=500, detail="Failed to process OAuth callback")

@router.get("/status")
async def oauth_status(
    connection_id: Optional[str] = Query(None, description="Connection ID to check"),
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (fallback to latest)")
):
    """Check OAuth connection status. If connection_id missing, returns latest active by tenant."""
    try:
        target_connection_id = connection_id
        if not target_connection_id and tenant_id:
            # Normalize tenant key to match storage format
            normalized_tenant = tenant_id.replace('-', '_')
            # Fetch latest connection for tenant
            conns = oauth_service.token_storage.get_connections_for_tenant(normalized_tenant)
            if conns:
                target_connection_id = conns[0]['connection_id']
            else:
                raise HTTPException(status_code=404, detail=f"No active connection found for tenant_id '{tenant_id}'")
        if not target_connection_id and not tenant_id:
            raise HTTPException(status_code=400, detail="Missing connection_id or tenant_id")

        # Test the connection
        test_result = await drive_service.test_connection(target_connection_id)
        
        return {
            'connection_id': target_connection_id,
            'valid': test_result['valid'],
            'error': test_result.get('error'),
            'user': test_result.get('user', {}),
            'storage': test_result.get('storage', {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check OAuth status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check OAuth status")

@router.get("/drive/list")
async def list_drive_folders(
    connection_id: str = Query(..., description="Connection ID"),
    folder_id: Optional[str] = Query(None, description="Folder ID (default: root)")
):
    """List folders in Google Drive"""
    try:
        folders = await drive_service.list_drive_folders(connection_id, folder_id)
        
        return {
            'connection_id': connection_id,
            'folder_id': folder_id or 'root',
            'folders': folders,
            'count': len(folders)
        }
        
    except Exception as e:
        logger.error(f"Failed to list Drive folders: {e}")
        raise HTTPException(status_code=500, detail="Failed to list Drive folders")

@router.get("/drive/files")
async def list_drive_files(
    connection_id: str = Query(..., description="Connection ID"),
    folder_id: Optional[str] = Query(None, description="Folder ID (default: root)"),
    file_types: Optional[str] = Query(None, description="Comma-separated file types")
):
    """List files in Google Drive folder"""
    try:
        # Parse file types if provided
        parsed_file_types = None
        if file_types:
            parsed_file_types = [t.strip() for t in file_types.split(',')]
        
        files = await drive_service.list_drive_files(connection_id, folder_id, parsed_file_types)
        
        return {
            'connection_id': connection_id,
            'folder_id': folder_id or 'root',
            'files': files,
            'count': len(files)
        }
        
    except Exception as e:
        logger.error(f"Failed to list Drive files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list Drive files")

@router.get("/drive/search")
async def search_drive_files(
    connection_id: str = Query(..., description="Connection ID"),
    query: str = Query(..., description="Search query"),
    folder_id: Optional[str] = Query(None, description="Folder ID to search in")
):
    """Search for files in Google Drive"""
    try:
        files = await drive_service.search_files(connection_id, query, folder_id)
        
        return {
            'connection_id': connection_id,
            'query': query,
            'folder_id': folder_id,
            'files': files,
            'count': len(files)
        }
        
    except Exception as e:
        logger.error(f"Failed to search Drive files: {e}")
        raise HTTPException(status_code=500, detail="Failed to search Drive files")

@router.delete("/revoke")
async def revoke_oauth_connection(
    connection_id: str = Query(..., description="Connection ID to revoke")
):
    """Revoke OAuth connection"""
    try:
        success = await oauth_service.revoke_token(connection_id)
        
        if success:
            return {
                'connection_id': connection_id,
                'status': 'revoked',
                'message': 'Connection revoked successfully'
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to revoke connection")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke OAuth connection: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke OAuth connection")

@router.get("/connections")
async def list_oauth_connections(
    tenant: str = Query(..., description="Tenant identifier")
):
    """List OAuth connections for a tenant"""
    try:
        connections = oauth_service.token_storage.get_connections_for_tenant(tenant)
        
        return {
            'tenant': tenant,
            'connections': connections,
            'count': len(connections)
        }
        
    except Exception as e:
        logger.error(f"Failed to list OAuth connections: {e}")
        raise HTTPException(status_code=500, detail="Failed to list OAuth connections")

# Plugin compatibility endpoints

@router.post("/authorize")
async def authorize_endpoint(
    request: Request,
    tenant: Optional[str] = Query(None, description="Tenant identifier"),
    site_id: Optional[str] = Query(None, description="Site identifier"),
    return_url_q: Optional[str] = Query(None, alias="return_url", description="Return URL (query param)"),
    login_hint: Optional[str] = Query(None, description="Email hint for Google login")
):
    """Return Google OAuth URL (plugin expects POST /oauth/authorize).
    Accepts JSON body: {"callback_url": "...", "tenant": "...", "site_id": "..."}
    Also supports query params for backward compatibility.
    """
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            body = {}

        # Prefer body fields, fallback to query params
        return_url = body.get("callback_url") or body.get("return_url") or return_url_q
        tenant_val = body.get("tenant") or tenant
        site_id_val = body.get("site_id") or site_id
        login_hint_val = body.get("login_hint") or login_hint

        if not return_url:
            raise HTTPException(status_code=400, detail="Missing callback_url/return_url")

        # Derive tenant/site_id from return_url if missing (plugin compatibility)
        if not tenant_val or not site_id_val:
            try:
                parsed = urlparse(return_url)
                host = parsed.netloc.lower()
                # Use full host as site_id, first label (or sanitized) as tenant
                derived_site_id = host
                first_label = host.split(':')[0].split('.')[0] if host else 'site'
                derived_tenant = first_label.replace('-', '_')
                tenant_val = tenant_val or derived_tenant
                site_id_val = site_id_val or derived_site_id
            except Exception:
                raise HTTPException(status_code=400, detail="Missing tenant or site_id")

        oauth_url, state = oauth_service.generate_oauth_url(
            tenant=tenant_val,
            site_id=site_id_val,
            return_url=return_url,
            login_hint=login_hint_val
        )
        return {"authorize_url": oauth_url, "state": state}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate authorize URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate authorize URL")

@router.post("/disconnect")
async def disconnect_endpoint(
    connection_id: str = Query(..., description="Connection ID to revoke")
):
    """Revoke a connection (plugin expects POST /oauth/disconnect)."""
    try:
        success = await oauth_service.revoke_token(connection_id)
        if success:
            return {"connection_id": connection_id, "status": "revoked"}
        raise HTTPException(status_code=400, detail="Failed to revoke connection")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect")
