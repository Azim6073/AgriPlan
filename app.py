import os
from functools import wraps
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, g
)

from config import Config
from database import get_db, close_db, init_db
from models import create_user, authenticate_user, get_user_by_id
from conflict_detector import (
    detect_all_conflicts, can_task_start, check_circular_dependency,
    validate_task_dates, parse_iso
)
from rescheduler import get_task_reschedule_suggestions, apply_reschedule
from scheduler import get_dashboard_data, refresh_task_statuses, generate_system_notifications
from demo_data import seed_demo_data

app = Flask(__name__)
app.config.from_object(Config)

# Register database teardown
app.teardown_appcontext(close_db)

# Ensure database exists
with app.app_context():
    init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = get_user_by_id(user_id)
        if g.user:
            # Also load unread notification count
            db = get_db()
            notif_count = db.execute(
                "SELECT COUNT(*) AS count FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,)
            ).fetchone()['count']
            g.unread_notifs = notif_count
            
            # Active conflicts count for sidebar badge
            active_conflicts = detect_all_conflicts(user_id, db)
            g.active_conflicts_count = len(active_conflicts)

# -------------------------------------------------------------
# LANDING & AUTHENTICATION ROUTES
# -------------------------------------------------------------

@app.route('/')
def index():
    if g.user:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        user, error = authenticate_user(email, password)
        if error:
            flash(error, 'error')
        else:
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash(f"Welcome back, {user['name']}!", 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not name or not email or not password:
            flash("All fields are required.", 'error')
        elif len(password) < 6:
            flash("Password must be at least 6 characters long.", 'error')
        elif password != confirm_password:
            flash("Passwords do not match.", 'error')
        else:
            user_id, error = create_user(name, email, password)
            if error:
                flash(error, 'error')
            else:
                session.clear()
                session['user_id'] = user_id
                session['user_name'] = name
                flash("Registration successful! Welcome to AgriPlan.", 'success')
                return redirect(url_for('dashboard'))
                
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out.", 'info')
    return redirect(url_for('login'))

# -------------------------------------------------------------
# DASHBOARD
# -------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    data = get_dashboard_data(g.user['id'], db)
    return render_template('dashboard.html', **data)

# -------------------------------------------------------------
# FIELD MANAGEMENT
# -------------------------------------------------------------

@app.route('/fields')
@login_required
def fields():
    db = get_db()
    search = request.args.get('search', '').strip()
    
    query = """
        SELECT f.*, 
               COUNT(c.id) AS crop_count,
               GROUP_CONCAT(c.crop_name, ', ') AS crop_names
        FROM fields f
        LEFT JOIN crops c ON f.id = c.field_id
        WHERE f.user_id = ?
    """
    params = [g.user['id']]
    
    if search:
        query += " AND (f.field_name LIKE ? OR f.location LIKE ? OR f.soil_type LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])
        
    query += " GROUP BY f.id ORDER BY f.created_at DESC"
    fields_list = db.execute(query, params).fetchall()
    
    return render_template('fields.html', fields=fields_list, search=search)

@app.route('/fields/add', methods=['POST'])
@login_required
def add_field():
    db = get_db()
    field_name = request.form.get('field_name', '').strip()
    location = request.form.get('location', '').strip()
    size_str = request.form.get('size', '').strip()
    area_unit = request.form.get('area_unit', 'acres')
    soil_type = request.form.get('soil_type', '').strip()
    irrigation_type = request.form.get('irrigation_type', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not field_name:
        flash("Field name is required.", 'error')
        return redirect(url_for('fields'))
        
    try:
        size = float(size_str)
        if size <= 0:
            flash("Field size must be greater than zero.", 'error')
            return redirect(url_for('fields'))
    except ValueError:
        flash("Invalid field size number.", 'error')
        return redirect(url_for('fields'))
        
    db.execute("""
        INSERT INTO fields (user_id, field_name, location, size, area_unit, soil_type, irrigation_type, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (g.user['id'], field_name, location, size, area_unit, soil_type, irrigation_type, notes))
    db.commit()
    
    flash(f"Field '{field_name}' created successfully!", 'success')
    return redirect(url_for('fields'))

@app.route('/fields/edit/<int:field_id>', methods=['POST'])
@login_required
def edit_field(field_id):
    db = get_db()
    field = db.execute("SELECT * FROM fields WHERE id = ? AND user_id = ?", (field_id, g.user['id'])).fetchone()
    if not field:
        flash("Field not found or access denied.", 'error')
        return redirect(url_for('fields'))
        
    field_name = request.form.get('field_name', '').strip()
    location = request.form.get('location', '').strip()
    size_str = request.form.get('size', '').strip()
    area_unit = request.form.get('area_unit', 'acres')
    soil_type = request.form.get('soil_type', '').strip()
    irrigation_type = request.form.get('irrigation_type', '').strip()
    notes = request.form.get('notes', '').strip()
    
    try:
        size = float(size_str)
        if size <= 0:
            flash("Field size must be greater than zero.", 'error')
            return redirect(url_for('fields'))
    except ValueError:
        flash("Invalid field size.", 'error')
        return redirect(url_for('fields'))
        
    db.execute("""
        UPDATE fields
        SET field_name = ?, location = ?, size = ?, area_unit = ?, soil_type = ?, irrigation_type = ?, notes = ?
        WHERE id = ? AND user_id = ?
    """, (field_name, location, size, area_unit, soil_type, irrigation_type, notes, field_id, g.user['id']))
    db.commit()
    
    flash(f"Field '{field_name}' updated successfully!", 'success')
    return redirect(url_for('fields'))

@app.route('/fields/delete/<int:field_id>', methods=['POST'])
@login_required
def delete_field(field_id):
    db = get_db()
    field = db.execute("SELECT * FROM fields WHERE id = ? AND user_id = ?", (field_id, g.user['id'])).fetchone()
    if not field:
        flash("Field not found or access denied.", 'error')
        return redirect(url_for('fields'))
        
    db.execute("DELETE FROM fields WHERE id = ? AND user_id = ?", (field_id, g.user['id']))
    db.commit()
    
    flash(f"Field '{field['field_name']}' and its associated tasks deleted.", 'info')
    return redirect(url_for('fields'))

# -------------------------------------------------------------
# CROP MANAGEMENT
# -------------------------------------------------------------

@app.route('/crops')
@login_required
def crops():
    db = get_db()
    field_filter = request.args.get('field_id', '')
    status_filter = request.args.get('status', '')
    
    query = """
        SELECT c.*, f.field_name, f.size AS field_size, f.area_unit
        FROM crops c
        JOIN fields f ON c.field_id = f.id
        WHERE c.user_id = ?
    """
    params = [g.user['id']]
    
    if field_filter:
        query += " AND c.field_id = ?"
        params.append(field_filter)
    if status_filter:
        query += " AND c.status = ?"
        params.append(status_filter)
        
    query += " ORDER BY c.sowing_date DESC"
    crops_list = db.execute(query, params).fetchall()
    
    user_fields = db.execute("SELECT id, field_name FROM fields WHERE user_id = ? ORDER BY field_name", (g.user['id'],)).fetchall()
    
    return render_template('crops.html', crops=crops_list, fields=user_fields, 
                           selected_field=field_filter, selected_status=status_filter)

@app.route('/crops/add', methods=['POST'])
@login_required
def add_crop():
    db = get_db()
    crop_name = request.form.get('crop_name', '').strip()
    field_id = request.form.get('field_id')
    variety = request.form.get('variety', '').strip()
    sowing_date = request.form.get('sowing_date')
    expected_harvest_date = request.form.get('expected_harvest_date')
    status = request.form.get('status', 'Growing')
    notes = request.form.get('notes', '').strip()
    
    if not crop_name or not field_id or not sowing_date or not expected_harvest_date:
        flash("Crop name, field, sowing date, and harvest date are required.", 'error')
        return redirect(url_for('crops'))
        
    # Validate field belongs to user
    field = db.execute("SELECT id FROM fields WHERE id = ? AND user_id = ?", (field_id, g.user['id'])).fetchone()
    if not field:
        flash("Selected field does not exist.", 'error')
        return redirect(url_for('crops'))
        
    if expected_harvest_date < sowing_date:
        flash("Expected harvest date cannot be earlier than sowing date.", 'error')
        return redirect(url_for('crops'))
        
    db.execute("""
        INSERT INTO crops (user_id, field_id, crop_name, variety, sowing_date, expected_harvest_date, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (g.user['id'], field_id, crop_name, variety, sowing_date, expected_harvest_date, status, notes))
    db.commit()
    
    flash(f"Crop '{crop_name}' added successfully!", 'success')
    return redirect(url_for('crops'))

@app.route('/crops/edit/<int:crop_id>', methods=['POST'])
@login_required
def edit_crop(crop_id):
    db = get_db()
    crop = db.execute("SELECT * FROM crops WHERE id = ? AND user_id = ?", (crop_id, g.user['id'])).fetchone()
    if not crop:
        flash("Crop not found or access denied.", 'error')
        return redirect(url_for('crops'))
        
    crop_name = request.form.get('crop_name', '').strip()
    field_id = request.form.get('field_id')
    variety = request.form.get('variety', '').strip()
    sowing_date = request.form.get('sowing_date')
    expected_harvest_date = request.form.get('expected_harvest_date')
    status = request.form.get('status', 'Growing')
    notes = request.form.get('notes', '').strip()
    
    if expected_harvest_date < sowing_date:
        flash("Expected harvest date cannot be earlier than sowing date.", 'error')
        return redirect(url_for('crops'))
        
    db.execute("""
        UPDATE crops
        SET crop_name = ?, field_id = ?, variety = ?, sowing_date = ?, expected_harvest_date = ?, status = ?, notes = ?
        WHERE id = ? AND user_id = ?
    """, (crop_name, field_id, variety, sowing_date, expected_harvest_date, status, notes, crop_id, g.user['id']))
    db.commit()
    
    flash(f"Crop '{crop_name}' updated successfully!", 'success')
    return redirect(url_for('crops'))

@app.route('/crops/delete/<int:crop_id>', methods=['POST'])
@login_required
def delete_crop(crop_id):
    db = get_db()
    crop = db.execute("SELECT * FROM crops WHERE id = ? AND user_id = ?", (crop_id, g.user['id'])).fetchone()
    if not crop:
        flash("Crop not found or access denied.", 'error')
        return redirect(url_for('crops'))
        
    db.execute("DELETE FROM crops WHERE id = ? AND user_id = ?", (crop_id, g.user['id']))
    db.commit()
    
    flash(f"Crop '{crop['crop_name']}' deleted.", 'info')
    return redirect(url_for('crops'))

# -------------------------------------------------------------
# WORKER & EQUIPMENT MANAGEMENT
# -------------------------------------------------------------

@app.route('/workers')
@login_required
def workers():
    db = get_db()
    workers_list = db.execute("""
        SELECT w.*, 
               COUNT(t.id) AS active_task_count
        FROM workers w
        LEFT JOIN tasks t ON w.id = t.assigned_worker_id AND t.status IN ('Pending', 'In Progress')
        WHERE w.user_id = ?
        GROUP BY w.id
        ORDER BY w.worker_name ASC
    """, (g.user['id'],)).fetchall()
    return render_template('workers.html', workers=workers_list)

@app.route('/workers/add', methods=['POST'])
@login_required
def add_worker():
    db = get_db()
    worker_name = request.form.get('worker_name', '').strip()
    contact = request.form.get('contact', '').strip()
    skills = request.form.get('skills', '').strip()
    availability_status = request.form.get('availability_status', 'Available')
    
    if not worker_name:
        flash("Worker name is required.", 'error')
        return redirect(url_for('workers'))
        
    db.execute("""
        INSERT INTO workers (user_id, worker_name, contact, skills, availability_status)
        VALUES (?, ?, ?, ?, ?)
    """, (g.user['id'], worker_name, contact, skills, availability_status))
    db.commit()
    
    flash(f"Worker '{worker_name}' added successfully!", 'success')
    return redirect(url_for('workers'))

@app.route('/workers/edit/<int:worker_id>', methods=['POST'])
@login_required
def edit_worker(worker_id):
    db = get_db()
    worker = db.execute("SELECT * FROM workers WHERE id = ? AND user_id = ?", (worker_id, g.user['id'])).fetchone()
    if not worker:
        flash("Worker not found or access denied.", 'error')
        return redirect(url_for('workers'))
        
    worker_name = request.form.get('worker_name', '').strip()
    contact = request.form.get('contact', '').strip()
    skills = request.form.get('skills', '').strip()
    availability_status = request.form.get('availability_status', 'Available')
    
    db.execute("""
        UPDATE workers
        SET worker_name = ?, contact = ?, skills = ?, availability_status = ?
        WHERE id = ? AND user_id = ?
    """, (worker_name, contact, skills, availability_status, worker_id, g.user['id']))
    db.commit()
    
    flash(f"Worker '{worker_name}' updated successfully!", 'success')
    return redirect(url_for('workers'))

@app.route('/workers/delete/<int:worker_id>', methods=['POST'])
@login_required
def delete_worker(worker_id):
    db = get_db()
    db.execute("DELETE FROM workers WHERE id = ? AND user_id = ?", (worker_id, g.user['id']))
    db.commit()
    flash("Worker record deleted successfully.", 'info')
    return redirect(url_for('workers'))

@app.route('/equipment')
@login_required
def equipment():
    db = get_db()
    equip_list = db.execute("""
        SELECT e.*, 
               COUNT(t.id) AS active_task_count
        FROM equipment e
        LEFT JOIN tasks t ON e.id = t.required_equipment_id AND t.status IN ('Pending', 'In Progress')
        WHERE e.user_id = ?
        GROUP BY e.id
        ORDER BY e.equipment_name ASC
    """, (g.user['id'],)).fetchall()
    return render_template('equipment.html', equipment=equip_list)

@app.route('/equipment/add', methods=['POST'])
@login_required
def add_equipment():
    db = get_db()
    equipment_name = request.form.get('equipment_name', '').strip()
    equipment_type = request.form.get('equipment_type', '').strip()
    identification_number = request.form.get('identification_number', '').strip()
    availability_status = request.form.get('availability_status', 'Available')
    maintenance_notes = request.form.get('maintenance_notes', '').strip()
    
    if not equipment_name or not equipment_type:
        flash("Equipment name and type are required.", 'error')
        return redirect(url_for('equipment'))
        
    db.execute("""
        INSERT INTO equipment (user_id, equipment_name, equipment_type, identification_number, availability_status, maintenance_notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (g.user['id'], equipment_name, equipment_type, identification_number, availability_status, maintenance_notes))
    db.commit()
    
    flash(f"Equipment '{equipment_name}' added successfully!", 'success')
    return redirect(url_for('equipment'))

@app.route('/equipment/edit/<int:equip_id>', methods=['POST'])
@login_required
def edit_equipment(equip_id):
    db = get_db()
    equipment_name = request.form.get('equipment_name', '').strip()
    equipment_type = request.form.get('equipment_type', '').strip()
    identification_number = request.form.get('identification_number', '').strip()
    availability_status = request.form.get('availability_status', 'Available')
    maintenance_notes = request.form.get('maintenance_notes', '').strip()
    
    db.execute("""
        UPDATE equipment
        SET equipment_name = ?, equipment_type = ?, identification_number = ?, availability_status = ?, maintenance_notes = ?
        WHERE id = ? AND user_id = ?
    """, (equipment_name, equipment_type, identification_number, availability_status, maintenance_notes, equip_id, g.user['id']))
    db.commit()
    
    flash(f"Equipment '{equipment_name}' updated successfully!", 'success')
    return redirect(url_for('equipment'))

@app.route('/equipment/delete/<int:equip_id>', methods=['POST'])
@login_required
def delete_equipment(equip_id):
    db = get_db()
    db.execute("DELETE FROM equipment WHERE id = ? AND user_id = ?", (equip_id, g.user['id']))
    db.commit()
    flash("Equipment record deleted successfully.", 'info')
    return redirect(url_for('equipment'))

# -------------------------------------------------------------
# TASK MANAGEMENT & SCHEDULING
# -------------------------------------------------------------

@app.route('/tasks')
@login_required
def tasks():
    db = get_db()
    refresh_task_statuses(g.user['id'], db)
    
    field_filter = request.args.get('field_id', '')
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    sort_by = request.args.get('sort', 'start_datetime')
    
    query = """
        SELECT t.*, f.field_name, c.crop_name, 
               w.worker_name, e.equipment_name,
               (SELECT COUNT(*) FROM task_dependencies WHERE task_id = t.id) AS prereq_count
        FROM tasks t
        JOIN fields f ON t.field_id = f.id
        LEFT JOIN crops c ON t.crop_id = c.id
        LEFT JOIN workers w ON t.assigned_worker_id = w.id
        LEFT JOIN equipment e ON t.required_equipment_id = e.id
        WHERE t.user_id = ?
    """
    params = [g.user['id']]
    
    if field_filter:
        query += " AND t.field_id = ?"
        params.append(field_filter)
    if status_filter:
        query += " AND t.status = ?"
        params.append(status_filter)
    if priority_filter:
        query += " AND t.priority = ?"
        params.append(priority_filter)
        
    if sort_by == 'deadline':
        query += " ORDER BY CASE WHEN t.deadline IS NULL THEN 1 ELSE 0 END, t.deadline ASC"
    elif sort_by == 'priority':
        query += " ORDER BY CASE t.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END ASC"
    else:
        query += " ORDER BY t.start_datetime ASC"
        
    tasks_list = db.execute(query, params).fetchall()
    
    # Active conflicts for badge indicators
    conflicts = detect_all_conflicts(g.user['id'], db)
    conflicted_task_ids = set()
    for c in conflicts:
        if c['task_id']:
            conflicted_task_ids.add(c['task_id'])
        if c['conflicting_task_id']:
            conflicted_task_ids.add(c['conflicting_task_id'])
            
    # Form options
    fields_list = db.execute("SELECT id, field_name FROM fields WHERE user_id = ? ORDER BY field_name", (g.user['id'],)).fetchall()
    crops_list = db.execute("SELECT id, crop_name, field_id FROM crops WHERE user_id = ? ORDER BY crop_name", (g.user['id'],)).fetchall()
    workers_list = db.execute("SELECT id, worker_name, skills FROM workers WHERE user_id = ? ORDER BY worker_name", (g.user['id'],)).fetchall()
    equip_list = db.execute("SELECT id, equipment_name, equipment_type FROM equipment WHERE user_id = ? ORDER BY equipment_name", (g.user['id'],)).fetchall()
    all_other_tasks = db.execute("SELECT id, title, start_datetime FROM tasks WHERE user_id = ? ORDER BY title", (g.user['id'],)).fetchall()
    
    return render_template(
        'tasks.html',
        tasks=tasks_list,
        conflicted_ids=conflicted_task_ids,
        fields=fields_list,
        crops=crops_list,
        workers=workers_list,
        equipment=equip_list,
        other_tasks=all_other_tasks,
        selected_field=field_filter,
        selected_status=status_filter,
        selected_priority=priority_filter,
        selected_sort=sort_by
    )

@app.route('/tasks/add', methods=['POST'])
@login_required
def add_task():
    db = get_db()
    title = request.form.get('title', '').strip()
    task_type = request.form.get('task_type', '').strip()
    field_id = request.form.get('field_id')
    crop_id = request.form.get('crop_id') or None
    description = request.form.get('description', '').strip()
    start_datetime = request.form.get('start_datetime')
    end_datetime = request.form.get('end_datetime')
    deadline = request.form.get('deadline') or None
    priority = request.form.get('priority', 'Medium')
    assigned_worker_id = request.form.get('assigned_worker_id') or None
    required_equipment_id = request.form.get('required_equipment_id') or None
    prerequisite_ids = request.form.getlist('prerequisites')
    
    if not title or not task_type or not field_id or not start_datetime or not end_datetime:
        flash("Title, task type, field, start time, and end time are required.", 'error')
        return redirect(url_for('tasks'))
        
    is_valid_dates, date_err = validate_task_dates(start_datetime, end_datetime, deadline)
    if not is_valid_dates:
        flash(date_err, 'error')
        return redirect(url_for('tasks'))
        
    cursor = db.execute("""
        INSERT INTO tasks (
            user_id, field_id, crop_id, title, task_type, description,
            start_datetime, end_datetime, deadline, priority,
            assigned_worker_id, required_equipment_id, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
    """, (
        g.user['id'], field_id, crop_id, title, task_type, description,
        start_datetime, end_datetime, deadline, priority,
        assigned_worker_id, required_equipment_id
    ))
    new_task_id = cursor.lastrowid
    
    # Save task dependencies
    for pid in prerequisite_ids:
        if pid and int(pid) != new_task_id:
            db.execute("""
                INSERT OR IGNORE INTO task_dependencies (task_id, prerequisite_task_id)
                VALUES (?, ?)
            """, (new_task_id, int(pid)))
            
    db.commit()
    
    # Check if newly created task triggered conflicts
    conflicts = detect_all_conflicts(g.user['id'], db)
    task_conflicts = [c for c in conflicts if c['task_id'] == new_task_id or c['conflicting_task_id'] == new_task_id]
    
    if task_conflicts:
        flash(f"Task '{title}' scheduled, but {len(task_conflicts)} conflict(s) detected! Check Conflict Management.", 'warning')
    else:
        flash(f"Task '{title}' scheduled successfully without conflicts!", 'success')
        
    return redirect(url_for('tasks'))

@app.route('/tasks/<int:task_id>')
@login_required
def get_task_details(task_id):
    db = get_db()
    task = db.execute("""
        SELECT t.*, f.field_name, c.crop_name, 
               w.worker_name, w.contact AS worker_contact,
               e.equipment_name, e.equipment_type
        FROM tasks t
        JOIN fields f ON t.field_id = f.id
        LEFT JOIN crops c ON t.crop_id = c.id
        LEFT JOIN workers w ON t.assigned_worker_id = w.id
        LEFT JOIN equipment e ON t.required_equipment_id = e.id
        WHERE t.id = ? AND t.user_id = ?
    """, (task_id, g.user['id'])).fetchone()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
        
    # Fetch prerequisites
    prereqs = db.execute("""
        SELECT t.id, t.title, t.status, t.start_datetime, t.end_datetime
        FROM task_dependencies td
        JOIN tasks t ON td.prerequisite_task_id = t.id
        WHERE td.task_id = ?
    """, (task_id,)).fetchall()
    
    # Fetch dependent tasks
    dependents = db.execute("""
        SELECT t.id, t.title, t.status
        FROM task_dependencies td
        JOIN tasks t ON td.task_id = t.id
        WHERE td.prerequisite_task_id = ?
    """, (task_id,)).fetchall()
    
    # Check startability
    can_start, start_reason = can_task_start(task_id, db)
    
    return jsonify({
        'task': dict(task),
        'prerequisites': [dict(p) for p in prereqs],
        'dependents': [dict(d) for d in dependents],
        'can_start': can_start,
        'start_reason': start_reason
    })

@app.route('/tasks/status/<int:task_id>', methods=['POST'])
@login_required
def update_task_status(task_id):
    db = get_db()
    new_status = request.form.get('status')
    
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id'])).fetchone()
    if not task:
        flash("Task not found or access denied.", 'error')
        return redirect(url_for('tasks'))
        
    # Enforce Dependency Rule: Cannot start if prerequisites are incomplete!
    if new_status == 'In Progress':
        can_start, reason = can_task_start(task_id, db)
        if not can_start:
            flash(f"Cannot start task '{task['title']}': {reason}", 'error')
            return redirect(url_for('tasks'))
            
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    completion_date = now_str if new_status == 'Completed' else None
    
    db.execute("""
        UPDATE tasks 
        SET status = ?, completion_date = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
    """, (new_status, completion_date, now_str, task_id, g.user['id']))
    db.commit()
    
    if new_status == 'Completed':
        flash(f"Great job! Task '{task['title']}' marked as Completed.", 'success')
    else:
        flash(f"Status for '{task['title']}' updated to {new_status}.", 'info')
        
    return redirect(request.referrer or url_for('tasks'))

@app.route('/tasks/edit/<int:task_id>', methods=['POST'])
@login_required
def edit_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id'])).fetchone()
    if not task:
        flash("Task not found or access denied.", 'error')
        return redirect(url_for('tasks'))
        
    title = request.form.get('title', '').strip()
    task_type = request.form.get('task_type', '').strip()
    field_id = request.form.get('field_id')
    crop_id = request.form.get('crop_id') or None
    description = request.form.get('description', '').strip()
    start_datetime = request.form.get('start_datetime')
    end_datetime = request.form.get('end_datetime')
    deadline = request.form.get('deadline') or None
    priority = request.form.get('priority', 'Medium')
    assigned_worker_id = request.form.get('assigned_worker_id') or None
    required_equipment_id = request.form.get('required_equipment_id') or None
    prerequisite_ids = request.form.getlist('prerequisites')
    
    is_valid_dates, date_err = validate_task_dates(start_datetime, end_datetime, deadline)
    if not is_valid_dates:
        flash(date_err, 'error')
        return redirect(url_for('tasks'))
        
    # Check circular dependencies
    for pid in prerequisite_ids:
        if pid:
            if check_circular_dependency(task_id, int(pid), db):
                flash("Circular dependency rejected: A task cannot directly or indirectly depend on itself.", 'error')
                return redirect(url_for('tasks'))
                
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("""
        UPDATE tasks 
        SET field_id = ?, crop_id = ?, title = ?, task_type = ?, description = ?,
            start_datetime = ?, end_datetime = ?, deadline = ?, priority = ?,
            assigned_worker_id = ?, required_equipment_id = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
    """, (
        field_id, crop_id, title, task_type, description,
        start_datetime, end_datetime, deadline, priority,
        assigned_worker_id, required_equipment_id, now_str,
        task_id, g.user['id']
    ))
    
    # Update dependencies
    db.execute("DELETE FROM task_dependencies WHERE task_id = ?", (task_id,))
    for pid in prerequisite_ids:
        if pid and int(pid) != task_id:
            db.execute("""
                INSERT OR IGNORE INTO task_dependencies (task_id, prerequisite_task_id)
                VALUES (?, ?)
            """, (task_id, int(pid)))
            
    db.commit()
    flash(f"Task '{title}' updated successfully!", 'success')
    return redirect(url_for('tasks'))

@app.route('/tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id'])).fetchone()
    if not task:
        flash("Task not found or access denied.", 'error')
        return redirect(url_for('tasks'))
        
    db.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id']))
    db.commit()
    flash(f"Task '{task['title']}' deleted.", 'info')
    return redirect(url_for('tasks'))

# -------------------------------------------------------------
# CONFLICT MANAGEMENT & SMART RESCHEDULING
# -------------------------------------------------------------

@app.route('/conflicts')
@login_required
def conflicts():
    db = get_db()
    refresh_task_statuses(g.user['id'], db)
    conflicts_list = detect_all_conflicts(g.user['id'], db)
    
    worker_conflicts = [c for c in conflicts_list if c['type'] == 'worker']
    equip_conflicts = [c for c in conflicts_list if c['type'] == 'equipment']
    dep_conflicts = [c for c in conflicts_list if c['type'] == 'dependency']
    deadline_conflicts = [c for c in conflicts_list if c['type'] == 'deadline']
    
    return render_template(
        'conflicts.html',
        conflicts=conflicts_list,
        worker_conflicts=worker_conflicts,
        equip_conflicts=equip_conflicts,
        dep_conflicts=dep_conflicts,
        deadline_conflicts=deadline_conflicts
    )

@app.route('/api/tasks/<int:task_id>/reschedule-suggestions')
@login_required
def api_reschedule_suggestions(task_id):
    db = get_db()
    result = get_task_reschedule_suggestions(task_id, g.user['id'], db)
    return jsonify(result)

@app.route('/api/tasks/<int:task_id>/reschedule', methods=['POST'])
@login_required
def api_apply_reschedule(task_id):
    db = get_db()
    data = request.get_json() or {}
    new_start = data.get('start_datetime')
    new_end = data.get('end_datetime')
    
    if not new_start or not new_end:
        return jsonify({'success': False, 'message': 'Missing new start or end time'}), 400
        
    result = apply_reschedule(task_id, new_start, new_end, g.user['id'], db)
    return jsonify(result)

# -------------------------------------------------------------
# CALENDAR & TIMELINE
# -------------------------------------------------------------

@app.route('/calendar')
@login_required
def calendar_view():
    db = get_db()
    fields_list = db.execute("SELECT id, field_name FROM fields WHERE user_id = ? ORDER BY field_name", (g.user['id'],)).fetchall()
    return render_template('calendar.html', fields=fields_list)

@app.route('/api/calendar-events')
@login_required
def api_calendar_events():
    db = get_db()
    refresh_task_statuses(g.user['id'], db)
    
    field_id = request.args.get('field_id')
    query = """
        SELECT t.*, f.field_name, c.crop_name, w.worker_name, e.equipment_name
        FROM tasks t
        JOIN fields f ON t.field_id = f.id
        LEFT JOIN crops c ON t.crop_id = c.id
        LEFT JOIN workers w ON t.assigned_worker_id = w.id
        LEFT JOIN equipment e ON t.required_equipment_id = e.id
        WHERE t.user_id = ?
    """
    params = [g.user['id']]
    if field_id:
        query += " AND t.field_id = ?"
        params.append(field_id)
        
    tasks_list = db.execute(query, params).fetchall()
    
    # Find conflicted IDs
    conflicts = detect_all_conflicts(g.user['id'], db)
    conflicted_ids = set()
    for c in conflicts:
        if c['task_id']:
            conflicted_ids.add(c['task_id'])
        if c['conflicting_task_id']:
            conflicted_ids.add(c['conflicting_task_id'])
            
    events = []
    for t in tasks_list:
        is_conflicted = t['id'] in conflicted_ids
        events.append({
            'id': t['id'],
            'title': t['title'],
            'task_type': t['task_type'],
            'field_name': t['field_name'],
            'crop_name': t['crop_name'] or 'None',
            'worker_name': t['worker_name'] or 'Unassigned',
            'equipment_name': t['equipment_name'] or 'None',
            'start': t['start_datetime'],
            'end': t['end_datetime'],
            'deadline': t['deadline'],
            'status': t['status'],
            'priority': t['priority'],
            'is_conflicted': is_conflicted
        })
        
    return jsonify(events)

# -------------------------------------------------------------
# NOTIFICATIONS
# -------------------------------------------------------------

@app.route('/notifications')
@login_required
def notifications():
    db = get_db()
    refresh_task_statuses(g.user['id'], db)
    generate_system_notifications(g.user['id'], db)
    
    notifs = db.execute("""
        SELECT n.*, t.title AS task_title
        FROM notifications n
        LEFT JOIN tasks t ON n.task_id = t.id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC
    """, (g.user['id'],)).fetchall()
    
    return render_template('notifications.html', notifications=notifs)

@app.route('/api/notifications/mark-read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, g.user['id']))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (g.user['id'],))
    db.commit()
    flash("All notifications marked as read.", 'info')
    return redirect(url_for('notifications'))

# -------------------------------------------------------------
# SETTINGS, PROFILE & DEMO DATA RESET
# -------------------------------------------------------------

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/settings/reset-demo', methods=['POST'])
@login_required
def reset_demo():
    db = get_db()
    seed_demo_data(db)
    flash("Demonstration data has been successfully re-seeded with all 6 scenarios!", 'success')
    return redirect(url_for('dashboard'))

@app.route('/settings/update-profile', methods=['POST'])
@login_required
def update_profile():
    db = get_db()
    name = request.form.get('name', '').strip()
    if not name:
        flash("Name cannot be empty.", 'error')
        return redirect(url_for('settings'))
        
    db.execute("UPDATE users SET name = ? WHERE id = ?", (name, g.user['id']))
    db.commit()
    session['user_name'] = name
    flash("Profile updated successfully!", 'success')
    return redirect(url_for('settings'))

# -------------------------------------------------------------
# APPLICATION ENTRYPOINT
# -------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
