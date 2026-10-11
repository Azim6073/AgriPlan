import os
import pytest
import sqlite3
from datetime import datetime, timedelta

from app import app
from database import init_db, get_db
from models import create_user, authenticate_user
from conflict_detector import (
    check_overlap, check_circular_dependency, can_task_start,
    detect_all_conflicts, validate_task_dates
)
from rescheduler import get_task_reschedule_suggestions, apply_reschedule
from scheduler import refresh_task_statuses

@pytest.fixture
def client_and_db(tmp_path):
    test_db = str(tmp_path / "test.db")
    app.config['TESTING'] = True
    app.config['DATABASE'] = test_db
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        init_db(db_path=test_db)
        
    with app.test_client() as c:
        yield c, test_db

# -------------------------------------------------------------
# 1. Registration and Login Test
# -------------------------------------------------------------
def test_user_registration_and_login(client_and_db):
    client, db_path = client_and_db
    
    # Register new user
    res = client.post('/register', data={
        'name': 'Test Farmer',
        'email': 'farmer@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Welcome to AgriPlan" in res.data or b"Dashboard" in res.data

    # Logout
    client.get('/logout')

    # Login with valid credentials
    res_login = client.post('/login', data={
        'email': 'farmer@test.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert res_login.status_code == 200
    assert b"Welcome back, Test Farmer!" in res_login.data

    # Login with wrong password
    client.get('/logout')
    res_fail = client.post('/login', data={
        'email': 'farmer@test.com',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert b"Invalid email or password" in res_fail.data

# -------------------------------------------------------------
# 2. Creating and Retrieving Fields
# -------------------------------------------------------------
def test_create_and_retrieve_fields(client_and_db):
    client, db_path = client_and_db
    
    client.post('/register', data={
        'name': 'Field Tester',
        'email': 'field@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })

    # Add field
    res_add = client.post('/fields/add', data={
        'field_name': 'Green Meadow',
        'location': 'North Valley',
        'size': '15.5',
        'area_unit': 'acres',
        'soil_type': 'Loamy Soil',
        'irrigation_type': 'Drip Irrigation',
        'notes': 'High organic matter'
    }, follow_redirects=True)
    assert res_add.status_code == 200
    assert b"Green Meadow" in res_add.data
    assert b"15.5" in res_add.data

# -------------------------------------------------------------
# 3. Creating and Updating Crops
# -------------------------------------------------------------
def test_create_and_update_crops(client_and_db):
    client, db_path = client_and_db
    
    client.post('/register', data={
        'name': 'Crop Tester',
        'email': 'crop@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })

    # Add field first
    client.post('/fields/add', data={
        'field_name': 'Plot A',
        'size': '5.0',
        'area_unit': 'acres'
    })

    # Add crop
    res_crop = client.post('/crops/add', data={
        'crop_name': 'Sweet Corn',
        'field_id': '1',
        'variety': 'Golden Bantam',
        'sowing_date': '2026-05-01',
        'expected_harvest_date': '2026-08-01',
        'status': 'Growing',
        'notes': 'Requires high nitrogen'
    }, follow_redirects=True)
    assert res_crop.status_code == 200
    assert b"Sweet Corn" in res_crop.data

    # Update crop
    res_edit = client.post('/crops/edit/1', data={
        'crop_name': 'Sweet Corn Hybrid',
        'field_id': '1',
        'variety': 'Golden Bantam F1',
        'sowing_date': '2026-05-01',
        'expected_harvest_date': '2026-08-01',
        'status': 'Flowering',
        'notes': 'Tasseling stage started'
    }, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"Sweet Corn Hybrid" in res_edit.data

# -------------------------------------------------------------
# 4. Creating Tasks
# -------------------------------------------------------------
def test_create_task(client_and_db):
    client, db_path = client_and_db
    
    client.post('/register', data={
        'name': 'Task Tester',
        'email': 'task@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })
    client.post('/fields/add', data={'field_name': 'Plot 1', 'size': '10.0'})

    res_task = client.post('/tasks/add', data={
        'title': 'Morning Irrigation',
        'task_type': 'Irrigation',
        'field_id': '1',
        'start_datetime': '2026-06-10T08:00',
        'end_datetime': '2026-06-10T10:00',
        'deadline': '2026-06-10T12:00',
        'priority': 'High'
    }, follow_redirects=True)
    assert res_task.status_code == 200
    assert b"Morning Irrigation" in res_task.data

# -------------------------------------------------------------
# 5. Overlapping Worker Conflict Detection
# -------------------------------------------------------------
def test_worker_conflict_detection(client_and_db):
    client, db_path = client_and_db
    
    client.post('/register', data={
        'name': 'Conflict Tester',
        'email': 'conflict@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })
    client.post('/fields/add', data={'field_name': 'Field 1', 'size': '10.0'})
    client.post('/fields/add', data={'field_name': 'Field 2', 'size': '12.0'})
    client.post('/workers/add', data={'worker_name': 'Worker Ramesh'})

    # Task 1: 09:00 - 11:00 assigned to Worker 1
    client.post('/tasks/add', data={
        'title': 'Task One',
        'task_type': 'Irrigation',
        'field_id': '1',
        'assigned_worker_id': '1',
        'start_datetime': '2026-07-01T09:00',
        'end_datetime': '2026-07-01T11:00'
    })

    # Task 2: 10:00 - 12:00 assigned to Worker 1 (Overlaps 10:00 - 11:00)
    client.post('/tasks/add', data={
        'title': 'Task Two',
        'task_type': 'Weeding',
        'field_id': '2',
        'assigned_worker_id': '1',
        'start_datetime': '2026-07-01T10:00',
        'end_datetime': '2026-07-01T12:00'
    })

    with app.app_context():
        db = get_db(db_path)
        conflicts = detect_all_conflicts(1, db)
        worker_conflicts = [c for c in conflicts if c['type'] == 'worker']
        assert len(worker_conflicts) == 1
        assert "Worker Double-Booking Conflict" in worker_conflicts[0]['title']
        assert "Worker Ramesh" in worker_conflicts[0]['resource_name']

# -------------------------------------------------------------
# 6. Overlapping Equipment Conflict Detection
# -------------------------------------------------------------
def test_equipment_conflict_detection(client_and_db):
    client, db_path = client_and_db
    
    client.post('/register', data={
        'name': 'Equip Tester',
        'email': 'equip@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })
    client.post('/fields/add', data={'field_name': 'Field A', 'size': '8.0'})
    client.post('/equipment/add', data={'equipment_name': 'Tractor TR-1', 'equipment_type': 'Tractor'})

    # Task A: 13:00 - 15:00 using Equipment 1
    client.post('/tasks/add', data={
        'title': 'Plowing Field A',
        'task_type': 'Other',
        'field_id': '1',
        'required_equipment_id': '1',
        'start_datetime': '2026-07-05T13:00',
        'end_datetime': '2026-07-05T15:00'
    })

    # Task B: 14:00 - 16:00 using Equipment 1
    client.post('/tasks/add', data={
        'title': 'Tilling Field A',
        'task_type': 'Other',
        'field_id': '1',
        'required_equipment_id': '1',
        'start_datetime': '2026-07-05T14:00',
        'end_datetime': '2026-07-05T16:00'
    })

    with app.app_context():
        db = get_db(db_path)
        conflicts = detect_all_conflicts(1, db)
        equip_conflicts = [c for c in conflicts if c['type'] == 'equipment']
        assert len(equip_conflicts) == 1
        assert "Equipment Conflict" in equip_conflicts[0]['title']
        assert "Tractor TR-1" in equip_conflicts[0]['resource_name']

# -------------------------------------------------------------
# 7. Validating Task Dependencies & Start Restrictions
# -------------------------------------------------------------
def test_task_dependency_validation(client_and_db):
    client, db_path = client_and_db
    
    client.post('/register', data={
        'name': 'Dep Tester',
        'email': 'dep@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })
    client.post('/fields/add', data={'field_name': 'North Parcel', 'size': '10.0'})

    # Task 1: Field prep (Pending)
    client.post('/tasks/add', data={
        'title': 'Prep Field',
        'task_type': 'Other',
        'field_id': '1',
        'start_datetime': '2026-08-01T08:00',
        'end_datetime': '2026-08-01T10:00'
    })

    # Task 2: Sow crop (Depends on Task 1)
    client.post('/tasks/add', data={
        'title': 'Sow Seeds',
        'task_type': 'Other',
        'field_id': '1',
        'start_datetime': '2026-08-01T11:00',
        'end_datetime': '2026-08-01T13:00',
        'prerequisites': ['1']
    })

    with app.app_context():
        db = get_db(db_path)
        can_start, reason = can_task_start(2, db)
        assert can_start is False
        assert "Prep Field" in reason

    # Attempt to start Task 2 while Task 1 is Pending -> Should be rejected
    res_start = client.post('/tasks/status/2', data={'status': 'In Progress'}, follow_redirects=True)
    assert b"Cannot start task" in res_start.data

    # Complete Task 1
    client.post('/tasks/status/1', data={'status': 'Completed'})

    # Now Task 2 can start!
    with app.app_context():
        db = get_db(db_path)
        can_start, reason = can_task_start(2, db)
        assert can_start is True

# -------------------------------------------------------------
# 8. Rejecting Circular Dependencies
# -------------------------------------------------------------
def test_circular_dependency_rejection(client_and_db):
    client, db_path = client_and_db
    
    with app.app_context():
        db = get_db(db_path)
        uid, _ = create_user("Cycle Tester", "cycle@test.com", "pass123", db)
        db.execute("INSERT INTO fields (user_id, field_name, size) VALUES (?, 'F1', 5)", (uid,))
        db.execute("INSERT INTO tasks (user_id, field_id, title, task_type, start_datetime, end_datetime) VALUES (?, 1, 'T1', 'Other', '2026-01-01T08:00', '2026-01-01T09:00')", (uid,))
        db.execute("INSERT INTO tasks (user_id, field_id, title, task_type, start_datetime, end_datetime) VALUES (?, 1, 'T2', 'Other', '2026-01-01T09:00', '2026-01-01T10:00')", (uid,))
        db.execute("INSERT INTO tasks (user_id, field_id, title, task_type, start_datetime, end_datetime) VALUES (?, 1, 'T3', 'Other', '2026-01-01T10:00', '2026-01-01T11:00')", (uid,))
        
        # T2 depends on T1
        db.execute("INSERT INTO task_dependencies (task_id, prerequisite_task_id) VALUES (2, 1)")
        # T3 depends on T2
        db.execute("INSERT INTO task_dependencies (task_id, prerequisite_task_id) VALUES (3, 2)")
        db.commit()

        # Check: Adding T1 depends on T3 creates cycle: T1 -> T3 -> T2 -> T1!
        assert check_circular_dependency(1, 3, db) is True
        # Check: Adding T1 depends on T1 (self-dependency)
        assert check_circular_dependency(1, 1, db) is True
        # Check: Adding T3 depends on T1 is valid (already transitively true, not circular)
        assert check_circular_dependency(3, 1, db) is False

# -------------------------------------------------------------
# 9. Identifying Overdue Tasks
# -------------------------------------------------------------
def test_identifying_overdue_tasks(client_and_db):
    client, db_path = client_and_db
    
    with app.app_context():
        db = get_db(db_path)
        uid, _ = create_user("Overdue Tester", "overdue@test.com", "pass123", db)
        db.execute("INSERT INTO fields (user_id, field_name, size) VALUES (?, 'F1', 5)", (uid,))
        
        past_time = "2020-01-01T10:00"
        past_deadline = "2020-01-01T12:00"
        
        # Pending task in past
        db.execute("""
            INSERT INTO tasks (user_id, field_id, title, task_type, start_datetime, end_datetime, deadline, status)
            VALUES (?, 1, 'Old Spraying', 'Pesticide or crop spraying', ?, ?, ?, 'Pending')
        """, (uid, past_time, past_time, past_deadline))
        
        # Completed task in past should NOT become overdue
        db.execute("""
            INSERT INTO tasks (user_id, field_id, title, task_type, start_datetime, end_datetime, deadline, status)
            VALUES (?, 1, 'Old Completed', 'Irrigation', ?, ?, ?, 'Completed')
        """, (uid, past_time, past_time, past_deadline))
        db.commit()

        refresh_task_statuses(uid, db)
        
        task1 = db.execute("SELECT status FROM tasks WHERE title = 'Old Spraying'").fetchone()
        task2 = db.execute("SELECT status FROM tasks WHERE title = 'Old Completed'").fetchone()
        assert task1['status'] == 'Overdue'
        assert task2['status'] == 'Completed'

# -------------------------------------------------------------
# 10. Finding an Available Alternative Time Slot (Rescheduler)
# -------------------------------------------------------------
def test_find_alternative_time_slots(client_and_db):
    client, db_path = client_and_db
    
    with app.app_context():
        db = get_db(db_path)
        uid, _ = create_user("Reschedule Tester", "resched@test.com", "pass123", db)
        db.execute("INSERT INTO fields (user_id, field_name, size) VALUES (?, 'F1', 5)", (uid,))
        db.execute("INSERT INTO workers (user_id, worker_name) VALUES (?, 'Worker Suresh')", (uid,))
        db.execute("INSERT INTO equipment (user_id, equipment_name, equipment_type) VALUES (?, 'Tractor 01', 'Tractor')", (uid,))
        
        tmrw = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Task 1: 08:00 - 11:00
        db.execute("""
            INSERT INTO tasks (user_id, field_id, title, task_type, start_datetime, end_datetime, deadline, assigned_worker_id, required_equipment_id)
            VALUES (?, 1, 'Busy Task', 'Other', ?, ?, ?, 1, 1)
        """, (uid, f"{tmrw}T08:00", f"{tmrw}T11:00", f"{tmrw}T18:00"))

        # Conflicted Task 2: 09:00 - 11:00 (duration 2h)
        cur = db.execute("""
            INSERT INTO tasks (user_id, field_id, title, task_type, start_datetime, end_datetime, deadline, assigned_worker_id, required_equipment_id)
            VALUES (?, 1, 'Conflicted Task', 'Other', ?, ?, ?, 1, 1)
        """, (uid, f"{tmrw}T09:00", f"{tmrw}T11:00", f"{tmrw}T18:00"))
        task2_id = cur.lastrowid
        db.commit()

        # Get suggestions
        res = get_task_reschedule_suggestions(task2_id, uid, db)
        assert res['success'] is True
        assert len(res['suggestions']) > 0
        
        # First suggestion should start at or after 11:00 when Worker Suresh & Tractor are free!
        sugg = res['suggestions'][0]
        assert sugg['start_datetime'] >= f"{tmrw}T11:00"
        assert sugg['duration_minutes'] == 120
        assert "Worker Suresh is available" in sugg['rationale']
        assert "Tractor 01 is ready" in sugg['rationale']

# -------------------------------------------------------------
# 11. Preventing Unauthorized Access to Another User's Records
# -------------------------------------------------------------
def test_unauthorized_user_isolation(client_and_db):
    client, db_path = client_and_db
    
    # Register Farmer 1
    client.post('/register', data={
        'name': 'Farmer One',
        'email': 'farmer1@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })
    client.post('/fields/add', data={'field_name': 'Secret Field Farmer 1', 'size': '50.0'})
    client.get('/logout')

    # Register Farmer 2
    client.post('/register', data={
        'name': 'Farmer Two',
        'email': 'farmer2@test.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })

    # Farmer 2 looks at fields page -> Must NOT see Farmer 1's field
    res_fields = client.get('/fields')
    assert b"Secret Field Farmer 1" not in res_fields.data

    # Farmer 2 tries to delete Farmer 1's field (ID 1)
    res_del = client.post('/fields/delete/1', follow_redirects=True)
    assert b"Field not found or access denied" in res_del.data

# -------------------------------------------------------------
# 12. Confirming that Rescheduling Updates the Database
# -------------------------------------------------------------
def test_reschedule_updates_database(client_and_db):
    client, db_path = client_and_db
    
    with app.app_context():
        db = get_db(db_path)
        uid, _ = create_user("Update Tester", "update@test.com", "pass123", db)
        db.execute("INSERT INTO fields (user_id, field_name, size) VALUES (?, 'F1', 5)", (uid,))
        cur = db.execute("""
            INSERT INTO tasks (user_id, field_id, title, task_type, start_datetime, end_datetime, deadline)
            VALUES (?, 1, 'Resched Me', 'Irrigation', '2026-09-01T08:00', '2026-09-01T10:00', '2026-09-01T18:00')
        """, (uid,))
        tid = cur.lastrowid
        db.commit()

        new_start = "2026-09-01T14:00"
        new_end = "2026-09-01T16:00"
        res = apply_reschedule(tid, new_start, new_end, uid, db)
        assert res['success'] is True

        updated_task = db.execute("SELECT start_datetime, end_datetime FROM tasks WHERE id = ?", (tid,)).fetchone()
        assert updated_task['start_datetime'] == new_start
        assert updated_task['end_datetime'] == new_end

        # Notification recorded
        notif = db.execute("SELECT * FROM notifications WHERE task_id = ?", (tid,)).fetchone()
        assert notif is not None
        assert "successfully rescheduled" in notif['message']
