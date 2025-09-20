#!/bin/bash

# Continuous Vercel logs monitoring script
# This script automatically restarts log monitoring every 4.5 minutes

DEPLOYMENT_URL="https://write-7ko82wi0k-mike-adgoios-projects.vercel.app"

echo "🚀 Starting continuous Vercel logs monitoring..."
echo "📍 Monitoring: $DEPLOYMENT_URL"
echo "⏱️  Will restart every 4.5 minutes to avoid timeout"
echo "🛑 Press Ctrl+C to stop"
echo ""

while true; do
    echo "$(date): Starting new log session..."
    echo "----------------------------------------"
    
    # Run logs and let them run until they timeout naturally (5 minutes)
    vercel logs "$DEPLOYMENT_URL" || true
    
    echo ""
    echo "$(date): Log session ended, restarting in 3 seconds..."
    echo "========================================"
    sleep 3
done
