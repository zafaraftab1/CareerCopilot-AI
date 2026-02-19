#!/bin/bash
# Installation and setup script for macOS/Linux

echo "=========================================="
echo "AI Job Application Agent - Setup Script"
echo "=========================================="
echo ""

# Check Python
echo "Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi
echo "✅ Python found: $(python3 --version)"
echo ""

# Create virtual environment
echo "Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Create .env file
echo "Creating configuration file..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ .env file created"
    echo "⚠️  Please edit .env with your configuration"
else
    echo "✅ .env file already exists"
fi
echo ""

# Initialize database
echo "Initializing database..."
python3 quickstart.py
echo ""

echo "=========================================="
echo "Setup Complete! ✅"
echo "=========================================="
echo ""
echo "To start the application, run:"
echo "  python3 app.py"
echo ""
echo "Then open your browser to:"
echo "  http://localhost:5000"
echo ""

