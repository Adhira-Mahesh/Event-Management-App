"""
Creates all database tables. Run this once before starting the app for the
first time (seed.py also calls this automatically, so running seed.py alone
is enough for local/demo setup).

Usage:
    python init_db.py
"""
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    db.create_all()
    print("Database tables created (or already existed).")
