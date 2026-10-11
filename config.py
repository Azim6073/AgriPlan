import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'agriplan-super-secret-key-cb029-nexmind-2026')
    DATABASE = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'agriplan.db'))
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1')
    TESTING = False
