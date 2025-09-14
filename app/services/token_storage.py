"""
Token Storage Service - SQLite-based secure token management
Handles encrypted storage and retrieval of Google OAuth tokens
"""

import sqlite3
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from cryptography.fernet import Fernet
import base64
import os

from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger

logger = get_logger(__name__)

class TokenStorage:
    """Secure token storage using SQLite with encryption"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_path = "oauth_storage.db"
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        self.init_database()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for token storage"""
        key_file = "oauth_encryption.key"
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            logger.info("Generated new encryption key for OAuth tokens")
            return key
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS google_connections (
                    id TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    user_email TEXT,
                    refresh_token_encrypted TEXT,
                    access_token_encrypted TEXT,
                    token_expires_at INTEGER,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    last_used_at INTEGER,
                    status TEXT DEFAULT 'active',
                    scopes TEXT DEFAULT 'https://www.googleapis.com/auth/drive.readonly'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    return_url TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    expires_at INTEGER
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant ON google_connections(tenant)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON google_connections(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON google_connections(user_email)")
            
            conn.commit()
            conn.close()
            logger.info("OAuth database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OAuth database: {e}")
            raise
    
    def _encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage"""
        if not token:
            return ""
        encrypted_bytes = self.cipher.encrypt(token.encode())
        return base64.b64encode(encrypted_bytes).decode()
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a token from storage"""
        if not encrypted_token:
            return ""
        try:
            encrypted_bytes = base64.b64decode(encrypted_token.encode())
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            return ""
    
    def store_oauth_state(self, state: str, tenant: str, site_id: str, return_url: str, nonce: str) -> bool:
        """Store OAuth state for CSRF protection"""
        try:
            conn = sqlite3.connect(self.db_path)
            expires_at = int((datetime.now() + timedelta(minutes=10)).timestamp())
            
            conn.execute("""
                INSERT OR REPLACE INTO oauth_states 
                (state, tenant, site_id, return_url, nonce, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (state, tenant, site_id, return_url, nonce, expires_at))
            
            conn.commit()
            conn.close()
            logger.info(f"Stored OAuth state for tenant {tenant}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OAuth state: {e}")
            return False
    
    def get_oauth_state(self, state: str) -> Optional[Dict]:
        """Retrieve and validate OAuth state"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("""
                SELECT tenant, site_id, return_url, nonce, expires_at
                FROM oauth_states WHERE state = ?
            """, (state,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            tenant, site_id, return_url, nonce, expires_at = row
            
            # Check if state has expired
            if datetime.now().timestamp() > expires_at:
                logger.warning(f"OAuth state {state} has expired")
                return None
            
            return {
                'tenant': tenant,
                'site_id': site_id,
                'return_url': return_url,
                'nonce': nonce
            }
            
        except Exception as e:
            logger.error(f"Failed to get OAuth state: {e}")
            return None
    
    def store_connection(self, connection_id: str, tenant: str, site_id: str, 
                       user_email: str, refresh_token: str, access_token: str = None,
                       expires_in: int = None) -> bool:
        """Store encrypted Google OAuth tokens"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            encrypted_refresh = self._encrypt_token(refresh_token)
            encrypted_access = self._encrypt_token(access_token) if access_token else ""
            
            token_expires_at = None
            if expires_in:
                token_expires_at = int((datetime.now() + timedelta(seconds=expires_in)).timestamp())
            
            conn.execute("""
                INSERT OR REPLACE INTO google_connections 
                (id, tenant, site_id, user_email, refresh_token_encrypted, 
                 access_token_encrypted, token_expires_at, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (connection_id, tenant, site_id, user_email, encrypted_refresh, 
                  encrypted_access, token_expires_at, int(datetime.now().timestamp())))
            
            conn.commit()
            conn.close()
            logger.info(f"Stored connection {connection_id} for tenant {tenant}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store connection: {e}")
            return False
    
    def get_connection(self, connection_id: str) -> Optional[Dict]:
        """Retrieve connection with decrypted tokens"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("""
                SELECT tenant, site_id, user_email, refresh_token_encrypted,
                       access_token_encrypted, token_expires_at, status, scopes
                FROM google_connections WHERE id = ? AND status = 'active'
            """, (connection_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            tenant, site_id, user_email, encrypted_refresh, encrypted_access, expires_at, status, scopes = row
            
            # Decrypt tokens
            refresh_token = self._decrypt_token(encrypted_refresh)
            access_token = self._decrypt_token(encrypted_access)
            
            return {
                'connection_id': connection_id,
                'tenant': tenant,
                'site_id': site_id,
                'user_email': user_email,
                'refresh_token': refresh_token,
                'access_token': access_token,
                'expires_at': expires_at,
                'status': status,
                'scopes': scopes
            }
            
        except Exception as e:
            logger.error(f"Failed to get connection: {e}")
            return None
    
    def update_access_token(self, connection_id: str, access_token: str, expires_in: int) -> bool:
        """Update access token for a connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            encrypted_access = self._encrypt_token(access_token)
            expires_at = int((datetime.now() + timedelta(seconds=expires_in)).timestamp())
            
            conn.execute("""
                UPDATE google_connections 
                SET access_token_encrypted = ?, token_expires_at = ?, last_used_at = ?
                WHERE id = ?
            """, (encrypted_access, expires_at, int(datetime.now().timestamp()), connection_id))
            
            conn.commit()
            conn.close()
            logger.info(f"Updated access token for connection {connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update access token: {e}")
            return False
    
    def revoke_connection(self, connection_id: str) -> bool:
        """Revoke a connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                UPDATE google_connections 
                SET status = 'revoked' 
                WHERE id = ?
            """, (connection_id,))
            
            conn.commit()
            conn.close()
            logger.info(f"Revoked connection {connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke connection: {e}")
            return False
    
    def get_connections_for_tenant(self, tenant: str) -> List[Dict]:
        """Get all active connections for a tenant"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("""
                SELECT id, site_id, user_email, created_at, last_used_at, status
                FROM google_connections 
                WHERE tenant = ? AND status = 'active'
                ORDER BY created_at DESC
            """, (tenant,))
            
            rows = cursor.fetchall()
            conn.close()
            
            connections = []
            for row in rows:
                connection_id, site_id, user_email, created_at, last_used_at, status = row
                connections.append({
                    'connection_id': connection_id,
                    'site_id': site_id,
                    'user_email': user_email,
                    'created_at': created_at,
                    'last_used_at': last_used_at,
                    'status': status
                })
            
            return connections
            
        except Exception as e:
            logger.error(f"Failed to get connections for tenant: {e}")
            return []
    
    def cleanup_expired_states(self):
        """Clean up expired OAuth states"""
        try:
            conn = sqlite3.connect(self.db_path)
            current_time = int(datetime.now().timestamp())
            
            cursor = conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (current_time,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired OAuth states")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired states: {e}")
    
    def get_connection_stats(self) -> Dict:
        """Get statistics about stored connections"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Total connections
            cursor = conn.execute("SELECT COUNT(*) FROM google_connections")
            total_connections = cursor.fetchone()[0]
            
            # Active connections
            cursor = conn.execute("SELECT COUNT(*) FROM google_connections WHERE status = 'active'")
            active_connections = cursor.fetchone()[0]
            
            # Connections by tenant
            cursor = conn.execute("""
                SELECT tenant, COUNT(*) as count 
                FROM google_connections 
                WHERE status = 'active'
                GROUP BY tenant
            """)
            tenant_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'total_connections': total_connections,
                'active_connections': active_connections,
                'tenant_stats': tenant_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get connection stats: {e}")
            return {'total_connections': 0, 'active_connections': 0, 'tenant_stats': {}}
