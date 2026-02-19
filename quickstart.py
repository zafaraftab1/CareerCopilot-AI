#!/usr/bin/env python
"""
Quick start script for AI Job Application Automation Agent
"""

import os
import sys

def check_python_version():
    """Check Python version"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        sys.exit(1)
    print("✅ Python version OK")

def check_venv():
    """Check if virtual environment is activated"""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment activated")
        return True
    else:
        print("⚠️  Virtual environment not detected")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import flask
        import flask_sqlalchemy
        import sqlalchemy
        print("✅ Core dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False

def initialize_database():
    """Initialize the database"""
    from app import create_app
    from models import db

    print("Initializing database...")
    app = create_app('development')
    with app.app_context():
        db.create_all()
        print("✅ Database initialized")

def setup_env():
    """Setup environment file"""
    if not os.path.exists('.env'):
        print("Creating .env file...")
        with open('.env', 'w') as f:
            with open('.env.example', 'r') as example:
                f.write(example.read())
        print("✅ .env file created. Please edit with your configuration.")
        return False
    else:
        print("✅ .env file exists")
        return True

def main():
    print("\n" + "="*60)
    print("AI Job Application Automation Agent - Quick Start")
    print("="*60 + "\n")

    # Checks
    check_python_version()
    check_venv()

    if not check_dependencies():
        print("\n❌ Please install dependencies first:")
        print("   pip install -r requirements.txt")
        sys.exit(1)

    # Setup
    env_ok = setup_env()

    # Initialize database
    try:
        initialize_database()
    except Exception as e:
        print(f"⚠️  Database initialization warning: {e}")

    print("\n" + "="*60)
    print("Setup Complete! ✅")
    print("="*60)
    print("\nNext steps:")
    print("1. Edit .env file with your configuration")
    print("2. Run: python app.py")
    print("3. Open: http://localhost:5000")
    print("\nFeatures:")
    print("  • Search jobs from multiple portals")
    print("  • Intelligent resume matching (70%+ threshold)")
    print("  • Automated job applications")
    print("  • Daily tracking and notifications")
    print("  • Modern dashboard interface")
    print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    main()

