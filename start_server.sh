#!/bin/bash

# MediaCrawler API Server Startup Script for Linux/Mac

echo "===================================="
echo "MediaCrawler API Server"
echo "===================================="
echo ""

echo "Starting API server at http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""

python3 server_main.py
