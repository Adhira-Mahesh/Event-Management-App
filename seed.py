"""
Populate the database with sample users (Admin, Student Organisers),
resources, events, and allocations for immediate testing.

Usage:
    python seed.py
"""
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Resource, Event, ResourceRequest, ResourceRequestItem
from app.services.booking_service import process_resource_request

app = create_app()

with app.app_context():
    db.create_all()

    # 1. Seed Users
    admin_user = User.query.filter_by(email="admin@college.edu").first()
    if not admin_user:
        admin_user = User(
            name="Adhira",
            email="adhira24comp@student.mes.ac.in",
            department="Campus Administration & Facilities",
            role="admin",
            is_active=True,
        )
        admin_user.set_password("123123")
        db.session.add(admin_user)
        print("Created Admin user: admin@college.edu (password: 123123)")

    student_1 = User.query.filter_by(email="alex.cs@college.edu").first()
    if not student_1:
        student_1 = User(
            name="Alex Rivera",
            email="alex.cs@college.edu",
            department="Computer Science Society",
            role="student_organiser",
            is_active=True,
        )
        student_1.set_password("student123")
        db.session.add(student_1)
        print("Created Student Organiser user: alex.cs@college.edu (password: student123)")

    student_2 = User.query.filter_by(email="sarah.arts@college.edu").first()
    if not student_2:
        student_2 = User(
            name="Sarah Chen",
            email="sarah.arts@college.edu",
            department="Fine Arts & Cultural Club",
            role="student_organiser",
            is_active=True,
        )
        student_2.set_password("student123")
        db.session.add(student_2)
        print("Created Student Organiser user: sarah.arts@college.edu (password: student123)")

    db.session.commit()

    # 2. Seed Resources
    if Resource.query.count() == 0:
        resources = [
            Resource(name="Main Auditorium (Grand Hall)", type="Auditorium", capacity=500, is_active=True),
            Resource(name="Auditorium West (Hall A)", type="Auditorium", capacity=150, is_active=True),
            Resource(name="Seminar Hall B", type="Auditorium", capacity=200, is_active=True),
            Resource(name="Computer Systems Lab 1", type="Laboratory", capacity=60, is_active=True),
            Resource(name="AI & Robotics Lab", type="Laboratory", capacity=40, is_active=True),
            Resource(name="Physics & Electronics Lab", type="Laboratory", capacity=45, is_active=True),
            Resource(name="4K Laser Projector Unit 1", type="Projector", capacity=None, is_active=True),
            Resource(name="Portable Projector Unit 2", type="Projector", capacity=None, is_active=True),
            Resource(name="Wireless UHF Microphone Set 1", type="Microphone", capacity=None, is_active=True),
            Resource(name="Podium Microphone Set 2", type="Microphone", capacity=None, is_active=True),
            Resource(name="Handheld Wireless Mic 3", type="Microphone", capacity=None, is_active=True),
            Resource(name="4K PTZ Broadcast Camera 1", type="Camera", capacity=None, is_active=True),
            Resource(name="DSLR Event Camera 2", type="Camera", capacity=None, is_active=True),
            Resource(name="High-Performance Workstation Hub", type="Computer", capacity=25, is_active=True),
            Resource(name="Legacy Overhead Projector (Decommissioned)", type="Projector", capacity=None, is_active=False),
        ]
        db.session.add_all(resources)
        db.session.commit()
        print(f"Added {len(resources)} sample facilities and AV equipment.")
    else:
        print("Resources already exist, skipping resource seed.")

    # 3. Seed Events & Multi-item Requests
    if Event.query.count() == 0:
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

        # Event 1: AI Hackathon 2026 (Tomorrow)
        ev1 = Event(
            name="Annual AI Hackathon 2026",
            organizer="Computer Science Society",
            expected_attendance=120,
            start_time=now + timedelta(days=1, hours=2),
            end_time=now + timedelta(days=1, hours=8),
            status="Approved",
            user_id=student_1.id,
        )
        db.session.add(ev1)
        db.session.flush()

        req1 = ResourceRequest(
            event_id=ev1.id,
            user_id=student_1.id,
            start_time=ev1.start_time,
            end_time=ev1.end_time,
            status="Pending",
        )
        db.session.add(req1)
        db.session.flush()

        db.session.add(ResourceRequestItem(request_id=req1.id, resource_type="Auditorium", quantity=1, min_capacity=120))
        db.session.add(ResourceRequestItem(request_id=req1.id, resource_type="Projector", quantity=1))
        db.session.add(ResourceRequestItem(request_id=req1.id, resource_type="Microphone", quantity=2))
        db.session.commit()

        # Approve and allocate req1
        process_resource_request(req1)

        # Event 2: Spring Cultural Fest Rehearsal (Day 3)
        ev2 = Event(
            name="Spring Cultural Showcase Rehearsal",
            organizer="Fine Arts & Cultural Club",
            expected_attendance=80,
            start_time=now + timedelta(days=3, hours=3),
            end_time=now + timedelta(days=3, hours=7),
            status="Approved",
            user_id=student_2.id,
        )
        db.session.add(ev2)
        db.session.flush()

        req2 = ResourceRequest(
            event_id=ev2.id,
            user_id=student_2.id,
            start_time=ev2.start_time,
            end_time=ev2.end_time,
            status="Pending",
        )
        db.session.add(req2)
        db.session.flush()

        db.session.add(ResourceRequestItem(request_id=req2.id, resource_type="Auditorium", quantity=1, min_capacity=80))
        db.session.add(ResourceRequestItem(request_id=req2.id, resource_type="Camera", quantity=1))
        db.session.commit()

        # Approve and allocate req2
        process_resource_request(req2)

        # Event 3: Cloud Computing Workshop (Day 5 - Pending Admin Review)
        ev3 = Event(
            name="Cloud Architecture Hands-on Workshop",
            organizer="Computer Science Society",
            expected_attendance=40,
            start_time=now + timedelta(days=5, hours=1),
            end_time=now + timedelta(days=5, hours=5),
            status="Pending",
            user_id=student_1.id,
        )
        db.session.add(ev3)
        db.session.flush()

        req3 = ResourceRequest(
            event_id=ev3.id,
            user_id=student_1.id,
            start_time=ev3.start_time,
            end_time=ev3.end_time,
            status="Pending",
        )
        db.session.add(req3)
        db.session.flush()

        db.session.add(ResourceRequestItem(request_id=req3.id, resource_type="Laboratory", quantity=1, min_capacity=40))
        db.session.add(ResourceRequestItem(request_id=req3.id, resource_type="Projector", quantity=1))
        db.session.add(ResourceRequestItem(request_id=req3.id, resource_type="Microphone", quantity=1))
        db.session.commit()

        print("Added sample events, requests, and automated allocations.")
    else:
        print("Events already exist, skipping event seed.")

    db.session.commit()
    print("Database seeding completed successfully.")

