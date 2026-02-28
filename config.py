import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///job_application.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email configuration
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'your-email@gmail.com')
    SENDER_PASSWORD = os.getenv('SENDER_PASSWORD', '')

    # Application limits
    DAILY_APPLICATION_LIMIT = 30
    MATCH_SCORE_THRESHOLD = 70

    # Candidate information
    CANDIDATE_NAME = 'MD Aftab Alam'
    CANDIDATE_EMAIL = 'aftab.work86@gmail.com'

    # Job portals
    JOB_PORTALS = ['naukri', 'linkedin', 'monster', 'indeed']
    PREFERRED_LOCATIONS = ['Hyderabad', 'Noida', 'Delhi NCR', 'Gurgaon', 'Mumbai', 'Kolkata']

    # Preferred roles
    PREFERRED_ROLES = [
        'Python Developer',
        'Python Software Developer',
        'AI Engineer',
        'Machine Learning Engineer',
        'Backend Developer'
    ]

    # Local LLM (Ollama) configuration
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2:3b')
    OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', OLLAMA_MODEL)

    # Naukri credentials for automated apply
    NAUKRI_EMAIL = os.getenv('NAUKRI_EMAIL', '')
    NAUKRI_PASSWORD = os.getenv('NAUKRI_PASSWORD', '')

    # Popup handling
    POPUP_WAIT_SECONDS    = 10  # seconds to wait for modal after Apply click
    OLLAMA_ANSWER_TIMEOUT = 20  # seconds for Ollama AI answer call

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
