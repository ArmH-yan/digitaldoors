#!/bin/bash
# Lead Generation Scraper - Unix Run Script

set -e

echo "========================================"
echo "Lead Generation Scraper"
echo "Armenian Construction Companies"
echo "========================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium

# Run the scraper
echo "Starting scraper..."
python main.py "$@"
