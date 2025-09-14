#!/usr/bin/env python3
"""
Real test script for document parsing using actual Google Drive files
This tests the complete pipeline with real files and validates usable chunks
"""

import asyncio
import sys
import os
import json

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.parser_service_optimized import ParserService
from app.services.google_drive_service import GoogleDriveService
from app.services.token_storage import TokenStorage

async def test_real_files_from_drive():
    """Test parsing using actual files from Google Drive"""
    
    print("🧪 Testing Document Parsing with REAL Google Drive Files")
    print("=" * 60)
    
    # Initialize services
    parser_service = ParserService()
    drive_service = GoogleDriveService()
    token_storage = TokenStorage()
    
    # Get real connection
    print("🔍 Looking for OAuth connections...")
    
    # Try to find a connection by checking the database
    try:
        # Get connections for the tenant
        connections = token_storage.get_connections_for_tenant("exciting_heisenberg_docingest")
        
        if not connections:
            print("❌ No OAuth connection found for exciting_heisenberg_docingest")
            print("   Please connect Google Drive through the plugin first")
            return False
            
        conn = connections[0]  # Use the first connection
        connection_id = conn['connection_id']
        tenant = "exciting_heisenberg_docingest"  # Use the tenant we searched for
        
        print(f"✅ Found connection: {connection_id}")
        print(f"🏢 Tenant: {tenant}")
        print(f"📧 User: {conn.get('user_email', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ Error finding connection: {e}")
        return False
    
    # Test with ExtremeCoatingsSMALLTest folder
    folder_name = "ExtremeCoatingsSMALLTest"
    folder_id = "1vvb_3rU67-DsIwLp02k4Lym7tvE-YAHW"  # The actual folder ID
    print(f"\n📁 Testing folder: {folder_name}")
    
    try:
        # List files in the SMALL test folder
        files = await drive_service.list_drive_files(connection_id, folder_id)
        
        if not files:
            print(f"❌ No files found in folder: {folder_name}")
            print("   Make sure the folder exists and contains files")
            return False
            
        print(f"✅ Found {len(files)} files in {folder_name}")
        
        # Show the files
        for i, file in enumerate(files[:5], 1):  # Show first 5 files
            print(f"   {i}. {file.get('name', 'Unknown')} ({file.get('mimeType', 'Unknown type')})")
        
        if len(files) > 5:
            print(f"   ... and {len(files) - 5} more files")
            
    except Exception as e:
        print(f"❌ Error listing files: {e}")
        return False
    
    print(f"\n📋 Testing {len(files)} REAL files...")
    
    success_count = 0
    error_count = 0
    total_chunks = 0
    total_pages = 0
    
    for i, file in enumerate(files, 1):
        filename = file.get('name', f'file_{i}')
        file_id = file.get('id', '')
        mime_type = file.get('mimeType', 'application/pdf')
        
        print(f"\n[{i}/{len(files)}] Testing: {filename}")
        print(f"   📄 File ID: {file_id}")
        print(f"   📋 MIME Type: {mime_type}")
        
        try:
            # Step 1: Download file from Google Drive
            print("  📥 Downloading from Google Drive...")
            content, actual_filename = await drive_service.download_file(connection_id, file_id)
            print(f"  ✅ Downloaded: {len(content):,} bytes")
            
            # Step 2: Parse document
            print("  🔍 Parsing document...")
            parsed_doc = parser_service.parse_document(content, mime_type, actual_filename)
            print(f"  ✅ Parsed: {len(parsed_doc.pages)} pages")
            
            # Step 3: Generate chunks directly from parsed document
            print("  ✂️  Generating chunks...")
            chunks = parser_service.chunk_document(parsed_doc)
            print(f"  ✅ Chunks: {len(chunks)}")
            
            # Step 4: Validate chunks have usable content
            usable_chunks = 0
            total_text_length = 0
            
            for chunk in chunks:
                if chunk.get('text', '').strip():
                    usable_chunks += 1
                    total_text_length += len(chunk['text'])
            
            print(f"  📊 Usable chunks: {usable_chunks}/{len(chunks)}")
            print(f"  📏 Total text length: {total_text_length:,} characters")
            
            # Step 5: Show sample content
            if usable_chunks > 0:
                sample_chunk = next((c for c in chunks if c.get('text', '').strip()), None)
                if sample_chunk:
                    sample_text = sample_chunk['text'][:300] + "..." if len(sample_chunk['text']) > 300 else sample_chunk['text']
                    print(f"  📝 Sample text: {sample_text}")
            
            # Validate success criteria
            if usable_chunks > 0 and total_text_length > 100:
                print(f"  ✅ SUCCESS: {filename} - {usable_chunks} usable chunks, {total_text_length:,} chars")
                success_count += 1
                total_chunks += usable_chunks
                total_pages += len(parsed_doc.pages)
            else:
                print(f"  ❌ FAILURE: {filename} - No usable content")
                error_count += 1
            
        except Exception as e:
            print(f"  ❌ ERROR: {filename}")
            print(f"     Error: {str(e)}")
            print(f"     Type: {type(e).__name__}")
            error_count += 1
    
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS:")
    print(f"   ✅ Successful files: {success_count}")
    print(f"   ❌ Failed files: {error_count}")
    print(f"   📈 Success Rate: {success_count/(success_count+error_count)*100:.1f}%")
    print(f"   📄 Total pages processed: {total_pages}")
    print(f"   ✂️  Total usable chunks: {total_chunks}")
    print(f"   📏 Average chunks per file: {total_chunks/success_count if success_count > 0 else 0:.1f}")
    
    if success_count > 0 and total_chunks > 0:
        print(f"\n🎉 SUCCESS! Parsing is working with real files!")
        print(f"   Generated {total_chunks} usable chunks from {success_count} files")
        return True
    else:
        print(f"\n💥 FAILURE! No usable content generated.")
        print(f"   This indicates a serious parsing problem.")
        return False

if __name__ == "__main__":
    print("🚀 Starting REAL Document Parsing Tests")
    print("=" * 60)
    
    # Test with real files from Google Drive
    success = asyncio.run(test_real_files_from_drive())
    
    if success:
        print("\n🎉 All tests passed! Ready for deployment.")
        sys.exit(0)
    else:
        print("\n💥 Tests failed. Fix parsing issues before deploying.")
        sys.exit(1)
