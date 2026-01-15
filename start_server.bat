@echo off
REM MediaCrawler API Server Startup Script for Windows

echo ====================================
echo MediaCrawler API Server
echo ====================================
echo.

echo Starting API server at http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

python server_main.py
