#!/bin/bash

# Continuous Vercel logs monitoring script
# Vercel CLI has a hard 5-minute limit that cannot be extended
# This script provides seamless restart with minimal downtime

DEPLOYMENT_URL="https://write-ckekd7k0b-mike-adgoios-projects.vercel.app"

echo "🚀 Starting continuous Vercel logs monitoring..."
echo "📍 Monitoring: $DEPLOYMENT_URL"
echo "⏱️  Vercel CLI limit: 5 minutes (cannot be extended)"
echo "🔄 Auto-restart: Immediate (1 second delay)"
echo "🛑 Press Ctrl+C to stop"
echo ""

while true; do
    echo "$(date): Starting new log session..."
    echo "----------------------------------------"
    
    # Run logs and let them run until they timeout naturally (5 minutes)
    vercel logs "$DEPLOYMENT_URL" || true
    
    echo ""
    echo "$(date): Log session ended, restarting in 1 second..."
    echo "========================================"
    sleep 1
done
