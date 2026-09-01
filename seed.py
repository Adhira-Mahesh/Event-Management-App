"""
Populate the database with sample resources and one demo event so you can
try the app immediately after setup.

Usage:
    python seed.py
"""
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import Resource, Event

app = create_app()

with app.app_context():
    db.create_all()

    if Resource.query.count() == 0:
        resources = [
            Resource(name="Main Auditorium", type="Auditorium", capacity=500, is_active=True),
            Resource(name="Hall A", type="Auditorium", capacity=150, is_active=True),
            Resource(name="Hall B", type="Auditorium", capacity=200, is_active=True),
            Resource(name="Computer Lab 1", type="Laboratory", capacity=60, is_active=True),
            Resource(name="Computer Lab 2", type="Laboratory", capacity=40, is_active=True),
            Resource(name="Projector Unit 1", type="Projector", capacity=None, is_active=True),
            Resource(name="Projector Unit 2", type="Projector", capacity=None, is_active=True),
            Resource(name="Microphone 1", type="Microphone", capacity=None, is_active=True),
            Resource(name="Microphone 2", type="Microphone", capacity=None, is_active=True),
            Resource(name="Microphone 3", type="Microphone", capacity=None, is_active=True),
            Resource(name="Camera Unit 1", type="Camera", capacity=None, is_active=True),
            Resource(name="Old Projector (retired)", type="Projector", capacity=None, is_active=False),
        ]
        db.session.add_all(resources)
        print(f"Added {len(resources)} sample resources.")
    else:
        print("Resources already exist, skipping resource seed.")

    if Event.query.count() == 0:
        now = datetime.utcnow()
        demo_event = Event(
            name="Technical Workshop",
            organizer="Computer Engineering Dept",
            expected_attendance=120,
            start_time=now + timedelta(days=7, hours=1),
            end_time=now + timedelta(days=7, hours=5),
            status="Pending",
        )
        db.session.add(demo_event)
        print("Added 1 sample event.")
    else:
        print("Events already exist, skipping event seed.")

    db.session.commit()
    print("Seed complete.")
