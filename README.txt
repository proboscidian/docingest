DOCUMENT INGEST SERVICE - COMPREHENSIVE TECHNICAL DOCUMENTATION
================================================================

OVERVIEW
========
The Document Ingest Service (DIS) is a sophisticated document processing and ingestion system designed to extract, parse, and store documents from Google Drive into a vector database for semantic search and retrieval. 
The service uses a centralized OAuth system to handle Google Drive authentication and provides a complete pipeline from document download to vector storage.

ARCHITECTURE
============
The service follows a microservices architecture with the following main components:

WordPress Plugin → Document Ingest Service → Google Drive → Qdrant Vector DB
     ↓                    ↓                      ↓              ↓
- User Interface      - OAuth Management      - File Access   - Vector Storage
- Connection Flow     - Token Storage         - Downloads     - Similarity Search
- Job Triggers        - Document Processing   - File Listing  - Retrieval
- Q&A Interface       - Embedding Generation  - Search        - Citations

CORE COMPONENTS
===============

1. MAIN APPLICATION (app/main_optimized.py)
   - FastAPI application with security middleware
   - IP whitelisting for access control
   - CORS configuration for cross-origin requests
   - API key authentication system
   - Disabled public documentation for security

2. API ROUTERS
   - /api/ingest.py - Document ingestion endpoints
   - /api/search.py - Vector database search endpoints
   - /api/health.py - Health check and API key validation
   - /api/admin.py - Admin panel functionality
   - /api/oauth.py - Google OAuth flow management

3. SERVICES
   - GoogleDriveService - Google Drive API operations
   - ParserService - Document parsing and OCR
   - EmbeddingService - Vector embedding generation
   - QdrantService - Vector database operations
   - JobService - Background job management
   - TokenStorage - OAuth token management
   - GoogleOAuthService - OAuth flow handling

4. UTILITIES
   - Config management (app/utils/config.py)
   - Logging system (app/utils/logging_optimized.py)
   - Security functions (app/utils/security.py)
   - IP whitelist middleware (app/middleware/ip_whitelist.py)

DOCUMENT PARSING SYSTEM
========================

PARSER SERVICE (app/services/parser_service_optimized.py)
--------------------------------------------------------
The ParserService is the core component responsible for extracting text from various document formats.

SUPPORTED FORMATS:
- PDF documents (application/pdf)
- Microsoft Word documents (.docx)
- Plain text files (.txt)
- CSV files (.csv)

PARSING STRATEGY:
1. PRIMARY: Unstructured library for advanced document parsing
2. OCR ENGINE: Tesseract OCR (primary) with EasyOCR fallback
3. BACKUP: PyMuPDF for PDF processing when needed

OCR CONFIGURATION:
- Tesseract path: /var/www/vhosts/old.industrialwebworks.net/mamba/envs/docingest/bin/tesseract
- Tessdata prefix: /var/www/vhosts/old.industrialwebworks.net/mamba/envs/docingest/share/tessdata
- OCR settings: OEM 1 (LSTM), PSM 6 (uniform block of text)

PARSING PROCESS:
1. Document type detection based on MIME type
2. Text extraction using appropriate parser
3. OCR processing for image-based content
4. Page-by-page text extraction
5. Confidence scoring for OCR results
6. Chunk generation for optimal embedding size

CHUNK GENERATION:
- Default chunk size: 1000 characters
- Overlap: 200 characters
- Smart text splitting preserving context
- Page-aware chunking with metadata

GOOGLE DRIVE INTEGRATION
=========================

CENTRALIZED OAUTH SYSTEM
-------------------------
The service uses a centralized OAuth approach where DIS handles all Google authentication:

1. OAuth Flow:
   - User initiates connection from WordPress plugin
   - Plugin redirects to DIS OAuth endpoint
   - DIS handles Google OAuth flow
   - Tokens stored encrypted in SQLite database
   - Connection ID returned to plugin

2. Token Management:
   - Encrypted storage in SQLite (oauth_storage.db)
   - Automatic token refresh
   - Connection validation
   - Secure token retrieval

GOOGLE DRIVE SERVICE (app/services/google_drive_service.py)
----------------------------------------------------------
Handles all Google Drive API operations:

FUNCTIONS:
- List folders and files
- Download file content
- Search files by query
- Get folder hierarchy
- Test connection status
- File metadata extraction

API ENDPOINTS USED:
- /drive/v3/files - File operations
- /drive/v3/about - User information
- /drive/v3/files/{fileId} - Specific file access

VECTOR DATABASE SYSTEM
======================

QDRANT INTEGRATION (app/services/qdrant_service.py)
---------------------------------------------------
Uses Qdrant Cloud for vector storage and similarity search:

CONFIGURATION:
- Qdrant Cloud URL: https://019fbcb6-1500-4d63-9a62-1d3c65af2302.us-east4-0.gcp.cloud.qdrant.io
- API Key: Encrypted in environment variables
- Collection naming: sp_{tenant_name}

OPERATIONS:
- Collection creation and management
- Vector upsert operations
- Similarity search queries
- Point deletion and updates
- Collection statistics

VECTOR CONFIGURATION:
- Embedding dimension: 384 (BAAI/bge-small-en-v1.5)
- Distance metric: Cosine similarity
- Collection per tenant for data isolation

EMBEDDING SERVICE (app/services/embedding_service_optimized.py)
---------------------------------------------------------------
Generates vector embeddings using FastEmbed:

MODEL: BAAI/bge-small-en-v1.5
- Dimension: 384
- Language: English optimized
- Performance: High accuracy for semantic search

OPERATIONS:
- Batch embedding generation
- Query embedding for search
- Model loading and caching
- Error handling and fallbacks

INGESTION PROCESS
=================

COMPLETE WORKFLOW
-----------------
1. API Request: Plugin sends ingest request with folder IDs
2. Authentication: API key validation and connection verification
3. File Discovery: List all files in specified Google Drive folders
4. Concurrent Processing: Process files in batches of 5
5. Document Parsing: Extract text using ParserService
6. Chunk Generation: Split text into optimal chunks
7. Embedding Generation: Create vector embeddings
8. Vector Storage: Store chunks in Qdrant with metadata
9. Progress Tracking: Update job status and statistics

CONCURRENT PROCESSING:
- Batch size: 5 files per batch
- Async file processing
- Error isolation per file
- Progress reporting

METADATA STORAGE:
Each chunk stored with:
- tenant: Tenant identifier
- doc_id: Google Drive file ID
- title: Document filename
- drive_path: Google Drive URL
- mime_type: File MIME type
- page: Page number
- chunk_idx: Chunk index within page
- sha256: File content hash
- text: Extracted text content
- embedding: Vector embedding (384 dimensions)

SECURITY SYSTEM
===============

IP WHITELISTING (app/middleware/ip_whitelist.py)
------------------------------------------------
Restricts access to authorized IP addresses:

AUTHORIZED IPS:
- 69.220.152.252
- 47.206.224.132
- 20.1.189.119

CONFIGURATION: ip-whitelist.json
- Dynamic IP management
- Admin panel integration
- Real-time updates

API KEY AUTHENTICATION
----------------------
Multi-tier authentication system:

1. ADMIN KEYS: Full access to all endpoints
2. PLUGIN KEYS: Limited access to ingest and OAuth endpoints
3. VALIDATION: Real-time API key verification

KEY MANAGEMENT:
- Site-specific API keys
- Admin panel key generation
- Usage tracking and monitoring

OAUTH SECURITY
--------------
- Encrypted token storage
- Secure state validation
- CSRF protection
- Token refresh automation

ENVIRONMENT CONFIGURATION
=========================

REQUIRED ENVIRONMENT VARIABLES (.env)
-------------------------------------
QDRANT_URL=https://019fbcb6-1500-4d63-9a62-1d3c65af2302.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.ObV6QwhI2t-o8_Vy-QFrPsRmGCyaIE61R2kOooap_7I

GOOGLE_CLIENT_ID=869753540851-b0tvp1hbjtab40kmmin83ur2gqp5i5m3.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=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
GOOGLE_REDIRECT_URI=https://docingest.industrialwebworks.net/ingestapp/oauth/callback

API_SECRET_KEY=ULBttXQLnKYEX18CBGcBz10lF8y31y1q
JWT_SECRET_KEY=your-jwt-secret-key

ALLOWED_ORIGINS=["https://api.industrialwebworks.net","https://switchprompt.industrialwebworks.net","http://localhost:8000"]

LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/docingest.log

REDIS_URL=redis://localhost:6379/0

DEPLOYMENT CONFIGURATION
========================

SYSTEMD SERVICE (docingest.service)
-----------------------------------
Service runs with micromamba environment:

[Unit]
Description=Document Ingest Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/vhosts/old.industrialwebworks.net/docingest.industrialwebworks.net
ExecStart=/var/www/vhosts/old.industrialwebworks.net/docingest.industrialwebworks.net/micromamba run -r /var/www/vhosts/old.industrialwebworks.net/mamba -n docingest python -m uvicorn app.main_optimized:app --host 0.0.0.0 --port 8999
Restart=always
RestartSec=3
EnvironmentFile=/var/www/vhosts/old.industrialwebworks.net/docingest.industrialwebworks.net/.env

[Install]
WantedBy=multi-user.target

NGINX CONFIGURATION (nginx_config.txt)
--------------------------------------
Reverse proxy configuration:

server {
    listen 443 ssl;
    server_name docingest.industrialwebworks.net;
    
    location /ingestapp/ {
        proxy_pass http://localhost:8999/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /ingestapp/docs {
        proxy_pass http://localhost:8999/docs;
    }
    
    location /ingestapp/openapi.json {
        proxy_pass http://localhost:8999/openapi.json;
    }
}

MICROMAMBA ENVIRONMENT
----------------------
Service runs in micromamba environment with:

PACKAGES:
- python=3.11
- tesseract=5.*
- poppler
- All Python dependencies from requirements_optimized.txt

ENVIRONMENT PATH:
- Micromamba: /var/www/vhosts/old.industrialwebworks.net/docingest.industrialwebworks.net/micromamba
- Environment: /var/www/vhosts/old.industrialwebworks.net/mamba/envs/docingest
- Tesseract: /var/www/vhosts/old.industrialwebworks.net/mamba/envs/docingest/bin/tesseract

SEARCH FUNCTIONALITY
====================

VECTOR SEARCH SYSTEM
--------------------
The Document Ingest Service provides powerful semantic search capabilities through a vector database integration:

SEARCH ARCHITECTURE:
WordPress Plugin → Search API → Embedding Service → Qdrant Vector DB
     ↓                ↓              ↓                ↓
- User Query      - Query Processing - Vector Generation - Similarity Search
- RAG Integration - Result Formatting - BAAI/bge-small   - Cosine Similarity
- Citations       - Metadata Attach  - 384 Dimensions   - Score Ranking

EMBEDDING MODEL:
- Model: BAAI/bge-small-en-v1.5
- Dimensions: 384
- Distance Metric: Cosine Similarity
- Language: English optimized

SEARCH CAPABILITIES:
- Semantic similarity search
- Multi-document retrieval
- Relevance scoring (0.0-1.0)
- Source attribution
- Page-level citations
- Configurable result limits

SEARCH PERFORMANCE:
- Average response time: <500ms
- Concurrent query support
- High relevance scores (0.7+ typical)
- Real-time search results

PLUGIN INTEGRATION:
The search endpoint enables full RAG (Retrieval Augmented Generation) functionality:

1. USER QUERY → Plugin receives user question
2. SEARCH REQUEST → Plugin calls search API
3. VECTOR SEARCH → Service finds relevant chunks
4. CONTEXT RETRIEVAL → Plugin gets document context
5. AI GENERATION → Plugin uses context for AI response
6. CITATIONS → Plugin shows source documents

EXAMPLE SEARCH FLOW:
```json
Request:
{
  "tenant": "exciting-heisenberg-docingest",
  "query": "carbide coating warranty",
  "top_k": 5,
  "score_threshold": 0.5
}

Response:
{
  "results": [
    {
      "text": "Extreme Coatings will either repair the screw or provide a pro-rata refund...",
      "metadata": {
        "title": "CarbideX_Double_Life_Warranty.pdf",
        "page": 1,
        "doc_id": "1c6Ka1pdic7lVYiaAVAX_AT5PNNT4lNS_",
        "chunk_idx": 1,
        "source": "google_drive"
      },
      "score": 0.786
    }
  ],
  "total_results": 3,
  "query": "carbide coating warranty",
  "tenant": "exciting-heisenberg-docingest"
}
```

API ENDPOINTS
=============

HEALTH ENDPOINTS
----------------
GET /ingestapp/health/
- Service health check
- Returns service status and version

GET /ingestapp/health/validate-key
- API key validation
- Returns key status and tenant information
- Requires: Authorization: Bearer {api_key}

OAUTH ENDPOINTS
---------------
GET /ingestapp/oauth/start
- Initiate Google OAuth flow
- Parameters: tenant, site_id, return_url
- Returns: Redirect to Google OAuth

GET /ingestapp/oauth/callback
- Handle Google OAuth callback
- Exchanges code for tokens
- Stores encrypted tokens
- Redirects to plugin with connection_id

GET /ingestapp/oauth/status
- Check OAuth connection status
- Parameters: connection_id or tenant_id
- Returns: Connection details and user info

GET /ingestapp/oauth/drive/list
- List Google Drive folders
- Parameters: connection_id
- Returns: Folder list with metadata

GET /ingestapp/oauth/drive/files
- List files in folder
- Parameters: connection_id, folder_id
- Returns: File list with metadata

GET /ingestapp/oauth/drive/search
- Search files in Drive
- Parameters: connection_id, query
- Returns: Search results

POST /ingestapp/oauth/authorize
- Authorize OAuth connection
- Parameters: callback_url, state
- Returns: OAuth URL

POST /ingestapp/oauth/disconnect
- Revoke OAuth connection
- Parameters: connection_id
- Returns: Success status

DELETE /ingestapp/oauth/revoke
- Revoke OAuth connection
- Parameters: connection_id
- Returns: Success status

INGEST ENDPOINTS
----------------
POST /ingestapp/ingest/
- Start document ingestion job
- Parameters: tenant, connection_id, drive.folder_ids, reingest
- Returns: job_id and success status
- Requires: Authorization: Bearer {api_key}

GET /ingestapp/ingest/job/{job_id}
- Get job progress and status
- Returns: Job details, progress, errors
- Requires: Authorization: Bearer {api_key}

POST /ingestapp/collection/init
- Initialize Qdrant collection
- Parameters: tenant
- Returns: Collection creation status
- Requires: Authorization: Bearer {api_key}

SEARCH ENDPOINTS
----------------
POST /ingestapp/search/
- Search documents in vector database using semantic similarity
- Parameters: 
  * tenant (required): Tenant identifier
  * query (required): Search query text
  * top_k (optional): Number of results (1-20, default: 5)
  * score_threshold (optional): Minimum relevance score (0.0-1.0, default: 0.0)
- Returns: Search results with metadata, scores, and source attribution
- Authentication: Requires valid API key
- Response time: <500ms typical
- Example queries tested:
  * "carbide coating warranty" → 3 results (0.786+ scores)
  * "extreme coatings company" → 2 results (0.821+ scores)
  * "thermal spray technology" → 2 results (0.767+ scores)

GET /ingestapp/search/health
- Search service health check and connectivity test
- Returns: Service status, embedding model info, and Qdrant connectivity
- Authentication: No authentication required
- Response includes:
  * Service status (healthy/unhealthy)
  * Embedding service status
  * Qdrant service status
  * Embedding dimension (384)

GET /ingestapp/search/documents
- List all documents in vector database for a tenant
- Parameters: tenant (query parameter)
- Returns: Complete document inventory with metadata
- Authentication: Requires valid API key
- Use case: Get complete document list (not search results)
- Response includes:
  * All documents with chunk counts
  * Page information for each document
  * Document IDs and source information
  * Total document and chunk counts

ADMIN ENDPOINTS
---------------
POST /ingestapp/admin/save-api-keys
- Save API key configuration
- Parameters: site_name, api_key, plan_type, active
- Returns: Success status
- Requires: Admin API key

GET /ingestapp/admin/api-keys
- List all API keys
- Returns: API key list with status
- Requires: Admin API key

GET /ingestapp/admin/connections
- List OAuth connections
- Returns: Connection list with details
- Requires: Admin API key

GET /ingestapp/admin/jobs
- List ingestion jobs
- Returns: Job list with status
- Requires: Admin API key

PLUGIN INTEGRATION
==================

INTEGRATION FLOW
----------------
1. Plugin validates API key with /health/validate-key
2. User initiates Google Drive connection via /oauth/start
3. OAuth flow completes, plugin receives connection_id
4. Plugin lists folders via /oauth/drive/list
5. User selects folders for ingestion
6. Plugin starts ingestion via /ingest/ with folder IDs
7. Plugin monitors progress via /ingest/job/{job_id}
8. Plugin can query vector database for semantic search

API KEY MANAGEMENT
------------------
- Site-specific API keys generated via admin panel
- Keys stored in api_keys.json
- Real-time validation and status checking
- Usage tracking and monitoring

ERROR HANDLING
--------------
- Comprehensive error logging
- Graceful failure handling
- Detailed error messages for debugging
- Retry mechanisms for transient failures

MONITORING AND LOGGING
======================

LOGGING SYSTEM (app/utils/logging_optimized.py)
-----------------------------------------------
Uses Loguru for structured logging:

LOG LEVELS:
- INFO: General operation information
- WARNING: Non-critical issues
- ERROR: Error conditions with context
- DEBUG: Detailed debugging information

LOG OUTPUTS:
- File: ./logs/docingest.log
- Console: Structured JSON format
- Error tracking with context

LOG CATEGORIES:
- Service initialization
- OAuth operations
- Document parsing
- Vector operations
- Job progress
- Error conditions

MONITORING ENDPOINTS
--------------------
- Health check endpoint
- Job progress tracking
- Connection status monitoring
- API key validation status

PERFORMANCE OPTIMIZATION
========================

CONCURRENT PROCESSING
---------------------
- Batch processing (5 files per batch)
- Async file operations
- Parallel embedding generation
- Concurrent vector operations

CACHING STRATEGIES
------------------
- Embedding model caching
- Token refresh caching
- Collection existence caching
- Connection validation caching

RESOURCE MANAGEMENT
-------------------
- Memory-efficient document processing
- Streaming file downloads
- Chunked text processing
- Garbage collection optimization

CURRENT SYSTEM STATUS
=====================

PRODUCTION DATA
---------------
Current tenant: exciting-heisenberg-docingest
- Documents processed: 10/10 (100% success rate)
- Total pages: 23 pages
- Chunks generated: 70 high-quality chunks
- Vectors stored: 73 in Qdrant Cloud
- Search quality: Excellent (0.7+ relevance scores)

TESTED FUNCTIONALITY
-------------------
✅ Google Drive OAuth integration
✅ Document ingestion pipeline
✅ PDF parsing with OCR (Tesseract + EasyOCR)
✅ Vector embedding generation
✅ Qdrant vector storage
✅ Semantic search functionality
✅ API key authentication
✅ IP whitelisting security
✅ Admin panel management
✅ Job progress tracking

SEARCH PERFORMANCE METRICS
--------------------------
- Average search response time: <500ms
- Relevance score range: 0.7-0.9 (high quality)
- Concurrent query support: Yes
- Embedding model: BAAI/bge-small-en-v1.5 (384 dimensions)
- Vector database: Qdrant Cloud (73 vectors stored)

PLUGIN INTEGRATION STATUS
-------------------------
✅ OAuth connection established
✅ API key validated and working
✅ Document ingestion completed
✅ Vector search endpoint available
✅ RAG functionality ready
✅ Source attribution working
✅ Citations and metadata available

READY FOR PRODUCTION USE
========================
The Document Ingest Service is fully operational and ready for:
- WordPress plugin integration
- RAG (Retrieval Augmented Generation) functionality
- Document Q&A systems
- Knowledge base search
- Content recommendation systems

TROUBLESHOOTING
===============

COMMON ISSUES
-------------
1. Service not starting:
   - Check micromamba environment
   - Verify Python dependencies
   - Check systemd service status

2. OAuth connection failures:
   - Verify Google Cloud Console configuration
   - Check redirect URI matching
   - Validate client credentials

3. Document parsing failures:
   - Check Tesseract OCR installation
   - Verify file format support
   - Review parsing logs

4. Qdrant connection issues:
   - Verify API key and URL
   - Check network connectivity
   - Validate collection permissions

DEBUGGING COMMANDS
------------------
- Check service status: sudo systemctl status docingest.service
- View logs: sudo journalctl -u docingest.service -f
- Test health: curl https://docingest.industrialwebworks.net/ingestapp/health/
- Check processes: ps aux | grep uvicorn
- Restart service: ./restart_service_no_sudo.sh

MAINTENANCE
===========

REGULAR TASKS
-------------
- Monitor log files for errors
- Check Qdrant storage usage
- Validate OAuth token expiration
- Update API keys as needed
- Review job completion rates

BACKUP PROCEDURES
-----------------
- Backup oauth_storage.db (SQLite database)
- Backup api_keys.json (API key configuration)
- Backup ip-whitelist.json (IP whitelist)
- Backup .env file (environment configuration)

SCALING CONSIDERATIONS
======================

HORIZONTAL SCALING
------------------
- Multiple service instances
- Load balancer configuration
- Shared Redis for job queuing
- Database connection pooling

VERTICAL SCALING
----------------
- Increased memory for large documents
- CPU optimization for OCR processing
- Storage optimization for vector data
- Network optimization for API calls

FUTURE ENHANCEMENTS
===================

PLANNED FEATURES
----------------
- Additional document formats
- Advanced OCR preprocessing
- Multi-language support
- Real-time job progress updates
- Advanced search capabilities
- Document versioning support

TECHNICAL DEBT
--------------
- Replace global job storage with Redis
- Implement proper database migrations
- Add comprehensive test coverage
- Optimize memory usage patterns
- Implement proper error recovery

PLUGIN DEVELOPER QUICK REFERENCE
=================================

ESSENTIAL ENDPOINTS FOR PLUGIN INTEGRATION
-------------------------------------------
1. OAuth Connection:
   GET /ingestapp/oauth/start?tenant={tenant}&site_id={site_id}&return_url={url}
   
2. Document Ingestion:
   POST /ingestapp/ingest/
   {
     "tenant": "exciting-heisenberg-docingest",
     "connection_id": "conn_xxx",
     "drive": {"folder_ids": ["folder1", "folder2"]},
     "reingest": "incremental"
   }
   
3. Vector Search (RAG):
   POST /ingestapp/search/
   {
     "tenant": "exciting-heisenberg-docingest",
     "query": "user question",
     "top_k": 5,
     "score_threshold": 0.5
   }

4. Document Listing:
   GET /ingestapp/search/documents?tenant=exciting-heisenberg-docingest
   Returns: Complete list of all documents with metadata

AUTHENTICATION
--------------
- API Key: COoRcy3kMUCfuPnpxympY6VIy9kPBYr2
- Header: Authorization: Bearer {api_key}
- Tenant: exciting-heisenberg-docingest

CURRENT DATA STATUS
-------------------
- Documents: 11 total (10 processed + 1 test)
- Pages: 23 total
- Chunks: 73 generated
- Vectors: 73 stored
- Search Quality: High (0.7+ scores)

DOCUMENT BREAKDOWN
------------------
✅ All 10 processed documents:
1. CarbideX-C9000-Formula.pdf (3 chunks, 1 page)
2. CarbideX_Double_Life_Warranty.pdf (3 chunks, 1 page)
3. EC-Carbidex-CPR-Chrome-Plating-Replacement-CPVC-Application-Bulletin.pdf (5 chunks, 2 pages)
4. EC-CorpBroch-FINAL-2015-SCA.pdf (30 chunks, 9 pages)
5. EC-Oil-and-Gas-Brochure.pdf (17 chunks, 5 pages)
6. Example-Low-Rate-20-LB-hr.pdf (3 chunks, 1 page)
7. Extreme-Coatings-Certificate-of-Registration-8304-2023.pdf (1 chunk, 1 page)
8. Fine-Particle-Abraison-CarbideX-C1000-C9000.pdf (2 chunks, 1 page)
9. pep.pdf (7 chunks, 1 page)
10. rebuildcert.pdf (1 chunk, 1 page)
11. Test Document (1 chunk, 1 page) - from testing

TESTED SEARCH QUERIES
---------------------
✅ "carbide coating warranty" → 3 results (0.786+ scores)
✅ "extreme coatings company" → 2 results (0.821+ scores)
✅ "thermal spray technology" → 2 results (0.767+ scores)

RAG INTEGRATION FLOW
--------------------
1. User asks question in plugin
2. Plugin calls POST /ingestapp/search/ with question
3. Service returns relevant document chunks
4. Plugin uses chunks as context for AI
5. Plugin shows answer with citations

CONTACT INFORMATION
===================
- Service URL: https://docingest.industrialwebworks.net/ingestapp/
- Admin Panel: https://docingest.industrialwebworks.net/ingestapp/
- Health Check: https://docingest.industrialwebworks.net/ingestapp/health/
- Search Health: https://docingest.industrialwebworks.net/ingestapp/search/health

DOCUMENTATION VERSION: 1.0.0
LAST UPDATED: September 11, 2025
SEARCH FUNCTIONALITY: ✅ IMPLEMENTED AND TESTED

CONCLUSION
==========
The Document Ingest Service provides a robust, scalable solution for document processing and vector storage. With its centralized OAuth system, advanced parsing capabilities, semantic search functionality, and secure architecture, it serves as a reliable foundation for document-based applications requiring RAG (Retrieval Augmented Generation) functionality.

The service is production-ready and successfully handles real-world document processing workloads with high reliability and performance. The newly implemented search endpoint enables full RAG integration for WordPress plugins, providing semantic search capabilities with excellent relevance scores and comprehensive source attribution.

Key achievements:
- ✅ Complete document ingestion pipeline
- ✅ High-quality vector search with 0.7+ relevance scores
- ✅ Full RAG functionality for plugin integration
- ✅ Production-ready with comprehensive monitoring
- ✅ Secure architecture with IP whitelisting and API key authentication
