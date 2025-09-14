#!/bin/bash

# Document Ingest Service Restart Script (No Sudo Required)
# This script restarts the service using the current user's permissions

echo "🔄 Restarting Document Ingest Service..."
echo "========================================"

# Check if we can access the service
echo "🔍 Checking current service status..."

# Kill any existing uvicorn processes
echo "⏹️  Stopping existing uvicorn processes..."
pkill -f "uvicorn app.main_optimized:app" || echo "No existing processes found"

# Wait a moment
sleep 2

# Start the service with micromamba environment
echo "▶️  Starting service with micromamba environment..."
nohup ./micromamba run -r /var/www/vhosts/old.industrialwebworks.net/mamba -n docingest python -m uvicorn app.main_optimized:app --host 0.0.0.0 --port 8999 > service.log 2>&1 &

# Wait for service to start
echo "⏳ Waiting for service to start..."
sleep 5

# Check if the service is running
if pgrep -f "uvicorn app.main_optimized:app" > /dev/null; then
    echo "✅ Service is running!"
    
    # Test the service health
    echo "🏥 Testing service health..."
    sleep 2
    
    # Test health endpoint
    if curl -s "https://docingest.industrialwebworks.net/ingestapp/health/" > /dev/null; then
        echo "✅ Health check passed!"
        
        # Test API key validation
        if curl -s -H "Authorization: Bearer COoRcy3kMUCfuPnpxympY6VIy9kPBYr2" "https://docingest.industrialwebworks.net/ingestapp/health/validate-key" > /dev/null; then
            echo "✅ API key validation working!"
            
            # Test OAuth status
            if curl -s -H "Authorization: Bearer COoRcy3kMUCfuPnpxympY6VIy9kPBYr2" "https://docingest.industrialwebworks.net/ingestapp/oauth/status?connection_id=conn_yW2NxYrZrroIHACYh-Ky6g" > /dev/null; then
                echo "✅ OAuth connection working!"
                echo ""
                echo "🎉 Service restart completed successfully!"
                echo "🚀 Ready to test ingest process!"
            else
                echo "❌ OAuth connection test failed"
            fi
        else
            echo "❌ API key validation test failed"
        fi
    else
        echo "❌ Health check failed"
    fi
else
    echo "❌ Service failed to start!"
    echo "📋 Check the logs with: tail -f service.log"
fi

echo ""
echo "📝 Next steps:"
echo "1. Test ingest process with a small folder"
echo "2. Check Qdrant for stored chunks"
echo "3. Verify plugin can access the data"
echo ""
echo "🔧 Useful commands:"
echo "• Check service status: ps aux | grep uvicorn"
echo "• View logs: tail -f service.log"
echo "• Test health: curl https://docingest.industrialwebworks.net/ingestapp/health/"
echo "• Stop service: pkill -f 'uvicorn app.main_optimized:app'"
echo ""
