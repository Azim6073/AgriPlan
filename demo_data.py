from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from database import get_db, init_db

def seed_demo_data(db=None):
    """
    Populates database with realistic sample demonstration data for Team NEXMIND.
    Ensures complete coverage of hackathon scenarios 1 through 6.
    """
    if db is None:
        db = get_db()
        
    init_db(db_conn=db)
    
    # 1. Ensure Demo User exists
    demo_email = "demo@agriplan.com"
    existing_user = db.execute("SELECT id FROM users WHERE email = ?", (demo_email,)).fetchone()
    if existing_user:
        user_id = existing_user['id']
        # Clear existing records for clean reset
        db.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM task_dependencies WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)", (user_id,))
        db.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM crops WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM fields WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM workers WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM equipment WHERE user_id = ?", (user_id,))
        db.commit()
    else:
        cursor = db.execute("""
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
        """, ("Demo Farmer (NEXMIND)", demo_email, generate_password_hash("demo123")))
        user_id = cursor.lastrowid
        db.commit()

    # 2. Create Fields
    fields_data = [
        ("North Field", "Sector 4A, Upper Valley", 12.5, "acres", "Loamy Soil", "Drip Irrigation", "Primary cereal and vegetable parcel with gentle southern slope."),
        ("South Field", "Plot 12, Canal Side", 18.0, "acres", "Clay Loam", "Sprinkler Irrigation", "Heavy moisture retention, ideal for seasonal maize rotation."),
        ("Vegetable Field", "Greenhouse Zone B", 6.2, "acres", "Sandy Loam", "Furrow & Micro-sprinkler", "Dedicated organic vegetable nursery and trellis beds.")
    ]
    field_ids = {}
    for name, loc, size, unit, soil, irrig, notes in fields_data:
        cur = db.execute("""
            INSERT INTO fields (user_id, field_name, location, size, area_unit, soil_type, irrigation_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, loc, size, unit, soil, irrig, notes))
        field_ids[name] = cur.lastrowid
    db.commit()

    # 3. Create Crops
    today = datetime.now().date()
    crops_data = [
        ("Wheat", field_ids["North Field"], "Kundan HD-2967", (today - timedelta(days=20)).isoformat(), (today + timedelta(days=90)).isoformat(), "Growing", "High yielding bread wheat variety; requires 4 irrigation cycles."),
        ("Maize", field_ids["South Field"], "Pioneer 3396", (today - timedelta(days=12)).isoformat(), (today + timedelta(days=65)).isoformat(), "Growing", "Hybrid corn; responds very well to split nitrogen doses."),
        ("Tomato", field_ids["Vegetable Field"], "Arka Rakshak", (today - timedelta(days=5)).isoformat(), (today + timedelta(days=55)).isoformat(), "Sown", "Disease-resistant determinate tomato; staked cultivation.")
    ]
    crop_ids = {}
    for name, f_id, variety, sow_d, harv_d, status, notes in crops_data:
        cur = db.execute("""
            INSERT INTO crops (user_id, field_id, crop_name, variety, sowing_date, expected_harvest_date, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, f_id, name, variety, sow_d, harv_d, status, notes))
        crop_ids[name] = cur.lastrowid
    db.commit()

    # 4. Create Workers
    workers_data = [
        ("Worker A (Ramesh)", "+91 98765 43210", "Tractor Operations, Irrigation, Field Prep", "Available"),
        ("Worker B (Suresh)", "+91 98765 43211", "Spraying, Fertilizer Application, Harvesting", "Available")
    ]
    worker_ids = {}
    for name, contact, skills, avail in workers_data:
        cur = db.execute("""
            INSERT INTO workers (user_id, worker_name, contact, skills, availability_status)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, name, contact, skills, avail))
        worker_ids[name] = cur.lastrowid
    db.commit()

    # 5. Create Equipment
    equip_data = [
        ("Tractor (John Deere 5050D)", "Tractor", "TR-01", "Available", "Full engine overhaul completed; 50 HP power."),
        ("Water Pump (Kirloskar 7.5HP)", "Water Pump", "WP-02", "Available", "High discharge flow; regular filter backwash."),
        ("Knapsack Power Sprayer", "Sprayer", "SP-03", "Available", "16L capacity motorized sprayer; 2 spare nozzles.")
    ]
    equip_ids = {}
    for name, eq_type, ident, avail, notes in equip_data:
        cur = db.execute("""
            INSERT INTO equipment (user_id, equipment_name, equipment_type, identification_number, availability_status, maintenance_notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, name, eq_type, ident, avail, notes))
        equip_ids[name] = cur.lastrowid
    db.commit()

    # 6. Create Tasks to exhibit the 6 specific Hackathon Scenarios
    # Reference times relative to today
    today_dt = datetime.combine(today, datetime.min.time())
    
    # Yesterday completed task (Scenario 6)
    yesterday_10 = (today_dt - timedelta(days=1)).replace(hour=9, minute=0).strftime("%Y-%m-%dT%H:%M")
    yesterday_12 = (today_dt - timedelta(days=1)).replace(hour=11, minute=30).strftime("%Y-%m-%dT%H:%M")
    db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status, completion_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["North Field"], crop_ids["Wheat"], "Soil Bed Leveling & Prep", "Other",
          "Laser land leveling completed prior to sowing.", yesterday_10, yesterday_12, yesterday_12, "Medium",
          worker_ids["Worker A (Ramesh)"], equip_ids["Tractor (John Deere 5050D)"], "Completed", yesterday_12))

    # Scenario 1: Normal scheduling (Today afternoon)
    t1_start = today_dt.replace(hour=14, minute=0).strftime("%Y-%m-%dT%H:%M")
    t1_end = today_dt.replace(hour=16, minute=0).strftime("%Y-%m-%dT%H:%M")
    t1_dead = today_dt.replace(hour=18, minute=0).strftime("%Y-%m-%dT%H:%M")
    db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["North Field"], crop_ids["Wheat"], "Routine Drip Irrigation Cycle", "Irrigation",
          "Apply 2-hour drip cycle with water soluble potassium fertilizer.", t1_start, t1_end, t1_dead, "Medium",
          worker_ids["Worker B (Suresh)"], equip_ids["Water Pump (Kirloskar 7.5HP)"], "Pending"))

    # Scenario 2: Worker Overlap Conflict (Tomorrow 10:00 - 12:00 vs 11:00 - 13:00 on Worker A)
    tmrw_dt = today_dt + timedelta(days=1)
    s2_a_start = tmrw_dt.replace(hour=10, minute=0).strftime("%Y-%m-%dT%H:%M")
    s2_a_end = tmrw_dt.replace(hour=12, minute=0).strftime("%Y-%m-%dT%H:%M")
    s2_a_dead = tmrw_dt.replace(hour=14, minute=0).strftime("%Y-%m-%dT%H:%M")
    cur_t2a = db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["Vegetable Field"], crop_ids["Tomato"], "Foliar Micronutrient Spraying", "Pesticide or crop spraying",
          "Spray zinc and boron mix on young tomato plants.", s2_a_start, s2_a_end, s2_a_dead, "High",
          worker_ids["Worker A (Ramesh)"], equip_ids["Knapsack Power Sprayer"], "Pending"))
    task2a_id = cur_t2a.lastrowid

    s2_b_start = tmrw_dt.replace(hour=11, minute=0).strftime("%Y-%m-%dT%H:%M")
    s2_b_end = tmrw_dt.replace(hour=13, minute=0).strftime("%Y-%m-%dT%H:%M")
    s2_b_dead = tmrw_dt.replace(hour=16, minute=0).strftime("%Y-%m-%dT%H:%M")
    db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["South Field"], crop_ids["Maize"], "Inter-row Weeding & Cultivation", "Weeding",
          "Mechanical weeding between maize rows using tractor cultivator.", s2_b_start, s2_b_end, s2_b_dead, "High",
          worker_ids["Worker A (Ramesh)"], equip_ids["Tractor (John Deere 5050D)"], "Pending"))

    # Scenario 3: Equipment Conflict (Day after tomorrow 09:00 - 11:30 vs 10:30 - 12:30 on Water Pump)
    day2_dt = today_dt + timedelta(days=2)
    s3_a_start = day2_dt.replace(hour=9, minute=0).strftime("%Y-%m-%dT%H:%M")
    s3_a_end = day2_dt.replace(hour=11, minute=30).strftime("%Y-%m-%dT%H:%M")
    s3_a_dead = day2_dt.replace(hour=14, minute=0).strftime("%Y-%m-%dT%H:%M")
    db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["South Field"], crop_ids["Maize"], "Heavy Sprinkler Irrigation", "Irrigation",
          "Run irrigation zones 1 and 2 for maize parcel.", s3_a_start, s3_a_end, s3_a_dead, "High",
          worker_ids["Worker B (Suresh)"], equip_ids["Water Pump (Kirloskar 7.5HP)"], "Pending"))

    s3_b_start = day2_dt.replace(hour=10, minute=30).strftime("%Y-%m-%dT%H:%M")
    s3_b_end = day2_dt.replace(hour=12, minute=30).strftime("%Y-%m-%dT%H:%M")
    s3_b_dead = day2_dt.replace(hour=16, minute=0).strftime("%Y-%m-%dT%H:%M")
    db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["Vegetable Field"], crop_ids["Tomato"], "Nursery Furrow Flooding", "Irrigation",
          "Flooding nursery furrows to ensure seed moisture.", s3_b_start, s3_b_end, s3_b_dead, "Critical",
          worker_ids["Worker A (Ramesh)"], equip_ids["Water Pump (Kirloskar 7.5HP)"], "Pending"))

    # Scenario 4: Dependency Validation & Timing Conflict
    # Prerequisite: "Deep Sub-Soil Tilling" (Day 3 08:00 - 11:00)
    day3_dt = today_dt + timedelta(days=3)
    p_start = day3_dt.replace(hour=8, minute=0).strftime("%Y-%m-%dT%H:%M")
    p_end = day3_dt.replace(hour=11, minute=0).strftime("%Y-%m-%dT%H:%M")
    cur_prereq = db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["North Field"], crop_ids["Wheat"], "Deep Sub-Soil Tilling", "Other",
          "Deep plowing before fertilizer incorporation.", p_start, p_end, p_end, "High",
          worker_ids["Worker A (Ramesh)"], equip_ids["Tractor (John Deere 5050D)"], "Pending"))
    prereq_id = cur_prereq.lastrowid

    # Dependent task: "DAP Fertilizer Top Dressing" scheduled prematurely at 09:30 - 11:30 (starts before prereq finishes at 11:00!)
    dep_start = day3_dt.replace(hour=9, minute=30).strftime("%Y-%m-%dT%H:%M")
    dep_end = day3_dt.replace(hour=11, minute=30).strftime("%Y-%m-%dT%H:%M")
    dep_dead = day3_dt.replace(hour=15, minute=0).strftime("%Y-%m-%dT%H:%M")
    cur_dep = db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["North Field"], crop_ids["Wheat"], "DAP Fertilizer Application", "Fertilizer application",
          "Incorporate Diammonium Phosphate into prepared seed bed.", dep_start, dep_end, dep_dead, "Critical",
          worker_ids["Worker B (Suresh)"], None, "Pending"))
    dep_id = cur_dep.lastrowid

    # Link dependency in DB
    db.execute("""
        INSERT INTO task_dependencies (task_id, prerequisite_task_id)
        VALUES (?, ?)
    """, (dep_id, prereq_id))

    # Scenario 5: Overdue task scenario (Deadline was 2 days ago)
    overdue_start = (today_dt - timedelta(days=2)).replace(hour=8, minute=0).strftime("%Y-%m-%dT%H:%M")
    overdue_end = (today_dt - timedelta(days=2)).replace(hour=10, minute=0).strftime("%Y-%m-%dT%H:%M")
    overdue_dead = (today_dt - timedelta(days=2)).replace(hour=12, minute=0).strftime("%Y-%m-%dT%H:%M")
    db.execute("""
        INSERT INTO tasks (user_id, field_id, crop_id, title, task_type, description, start_datetime, end_datetime, deadline, priority, assigned_worker_id, required_equipment_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, field_ids["Vegetable Field"], crop_ids["Tomato"], "Early Blight Fungicide Spray", "Pesticide or crop spraying",
          "Preventive spray against early tomato blight.", overdue_start, overdue_end, overdue_dead, "Critical",
          worker_ids["Worker B (Suresh)"], equip_ids["Knapsack Power Sprayer"], "Overdue"))

    # Initial Notifications
    db.execute("""
        INSERT INTO notifications (user_id, message, notification_type, is_read)
        VALUES (?, 'Welcome to AgriPlan! Demonstration data successfully loaded with 6 real farming test scenarios.', 'system', 0)
    """, (user_id,))
    
    db.commit()
    return user_id

if __name__ == '__main__':
    from config import Config
    import os
    os.makedirs('instance', exist_ok=True)
    db = get_db('instance/agriplan.db')
    uid = seed_demo_data(db)
    print(f"Sample demonstration data loaded for user_id={uid} (demo@agriplan.com / demo123)")
    db.close()
