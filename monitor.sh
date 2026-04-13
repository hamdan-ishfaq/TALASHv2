#!/bin/bash

# Real-time monitoring script for CV processing pipeline
# Shows: Backend upload → Worker processing → Frontend data fetch

echo "════════════════════════════════════════════════════════════════════════════════"
echo "🚀 CV PROCESSING PIPELINE MONITOR"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Watching: Backend Upload → Worker Processing → Frontend Data Fetch"
echo "Press CTRL+C to stop"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Use docker-compose logs with colored output
docker-compose logs -f --tail=0 2>&1 | while IFS= read -r line; do
    # Backend upload events
    if echo "$line" | grep -q "UPLOAD-START"; then
        echo ""
        echo "📤 [BACKEND] CV UPLOAD RECEIVED"
        echo "$line" | sed 's/^/   /'
    fi
    
    if echo "$line" | grep -q "UPLOAD"; then
        echo "$line" | sed 's/^/   /'
    fi
    
    # Worker task received
    if echo "$line" | grep -q "TASK-START"; then
        echo ""
        echo "🔄 [WORKER] TASK STARTED"
        echo "$line" | sed 's/^/   /'
    fi
    
    # Processing stages
    if echo "$line" | grep -q "STAGE-[0-9]"; then
        echo "$line" | sed 's/^/   /'
    fi
    
    # Page extraction
    if echo "$line" | grep -q "PAGE-"; then
        echo "$line" | sed 's/^/   /'
    fi
    
    # Database commits
    if echo "$line" | grep -q "STAGE-4-OK\|STAGE-5-OK"; then
        echo "✅ [WORKER] DATA COMMITTED TO DATABASE"
        echo "$line" | sed 's/^/   /'
    fi
    
    # Task completion
    if echo "$line" | grep -q "TASK-SUCCESS"; then
        echo ""
        echo "✅ [WORKER] TASK COMPLETED SUCCESSFULLY"
        echo "$line" | sed 's/^/   /'
    fi
    
    if echo "$line" | grep -q "TASK-RESULT"; then
        echo "$line" | sed 's/^/   /'
        echo ""
    fi
    
    # Ollama/LLM calls
    if echo "$line" | grep -q "HTTP Request.*Ollama\|llama3.1\|SUMMARY"; then
        echo "$line" | sed 's/^/   /'
    fi
done
