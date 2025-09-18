#!/bin/bash

# Build script for Vercel deployment

echo "🏗️  Building Write Aid for production..."

# Navigate to frontend directory
cd frontend

# Install dependencies
echo "📦 Installing frontend dependencies..."
npm install

# Build the React app
echo "⚛️  Building React application..."
npm run build

echo "✅ Build completed successfully!"
echo "📁 Built files are in frontend/build/"
