@echo off
REM Docker Run Script for Lead Generation Scraper

echo ========================================
echo Starting Lead Generation Scraper with Docker
echo ========================================

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed or not in PATH
    exit /b 1
)

REM Build and start services
echo Building and starting services...
docker-compose up -d --build

REM Show logs
echo.
echo Services started. Showing logs...
echo Press Ctrl+C to stop
echo.
docker-compose logs -f scraper
