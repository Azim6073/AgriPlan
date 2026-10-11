from datetime import datetime
from database import get_db

def parse_iso(dt_str):
    """Safely parse ISO datetime string (supports YYYY-MM-DDTHH:MM or YYYY-MM-DDTHH:MM:SS)."""
    if not dt_str:
        return None
    dt_str = dt_str.replace('Z', '')
    if 'T' in dt_str:
        parts = dt_str.split('T')
        date_part = parts[0]
        time_part = parts[1][:5] # take HH:MM
        return datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
    else:
        return datetime.strptime(dt_str[:16], "%Y-%m-%d %H:%M")

def check_overlap(start1, end1, start2, end2):
    """
    Two tasks overlap when:
    Task A start < Task B end AND Task B start < Task A end
    """
    s1 = parse_iso(start1)
    e1 = parse_iso(end1)
    s2 = parse_iso(start2)
    e2 = parse_iso(end2)
    if not (s1 and e1 and s2 and e2):
        return False
    return (s1 < e2) and (s2 < e1)

def check_circular_dependency(task_id, prerequisite_id, db):
    """
    Returns True if adding dependency (task_id depends on prerequisite_id)
    would create a circular dependency.
    A cycle is created if prerequisite_id already depends (directly or transitively) on task_id.
    """
    if str(task_id) == str(prerequisite_id):
        return True
        
    visited = set()
    queue = [int(prerequisite_id)]
    
    while queue:
        current = queue.pop(0)
        if current == int(task_id):
            return True
        if current in visited:
            continue
        visited.add(current)
        
        # Find all prerequisites of current
        rows = db.execute(
            "SELECT prerequisite_task_id FROM task_dependencies WHERE task_id = ?",
            (current,)
        ).fetchall()
        for row in rows:
            queue.append(row['prerequisite_task_id'])
            
    return False

def can_task_start(task_id, db):
    """
    Check if a task can be started.
    Returns (can_start: bool, reason: str).
    A task cannot start if any prerequisite task is not completed.
    """
    prereqs = db.execute("""
        SELECT t.id, t.title, t.status 
        FROM task_dependencies td
        JOIN tasks t ON td.prerequisite_task_id = t.id
        WHERE td.task_id = ?
    """, (task_id,)).fetchall()
    
    for p in prereqs:
        if p['status'] != 'Completed':
            return False, f"Prerequisite task '{p['title']}' is currently {p['status']}. It must be Completed first."
            
    return True, "All prerequisite tasks are completed."

def detect_all_conflicts(user_id, db=None):
    """
    Run comprehensive rule-based conflict detection for a user.
    Returns list of conflict dictionaries.
    """
    if db is None:
        db = get_db()
        
    conflicts = []
    
    # Fetch active tasks
    tasks = db.execute("""
        SELECT t.*, f.field_name, 
               w.worker_name, 
               e.equipment_name, e.equipment_type
        FROM tasks t
        JOIN fields f ON t.field_id = f.id
        LEFT JOIN workers w ON t.assigned_worker_id = w.id
        LEFT JOIN equipment e ON t.required_equipment_id = e.id
        WHERE t.user_id = ? AND t.status NOT IN ('Completed', 'Cancelled')
        ORDER BY t.start_datetime ASC
    """, (user_id,)).fetchall()
    
    task_map = {t['id']: dict(t) for t in tasks}
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
    now_dt = datetime.now()

    # 1. Check Overlapping Worker Conflicts & Equipment Conflicts
    num_tasks = len(tasks)
    seen_worker_pairs = set()
    seen_equip_pairs = set()
    
    for i in range(num_tasks):
        t1 = tasks[i]
        
        # Deadline conflict for t1
        if t1['deadline']:
            end_dt = parse_iso(t1['end_datetime'])
            dead_dt = parse_iso(t1['deadline'])
            if end_dt and dead_dt and end_dt > dead_dt:
                conflicts.append({
                    'id': f"deadline-{t1['id']}",
                    'type': 'deadline',
                    'title': 'Deadline Exceeded Warning',
                    'description': f"Task '{t1['title']}' is scheduled to finish at {t1['end_datetime'].replace('T', ' ')}, which is after its deadline {t1['deadline'].replace('T', ' ')}.",
                    'task_id': t1['id'],
                    'task_title': t1['title'],
                    'field_name': t1['field_name'],
                    'conflicting_task_id': None,
                    'conflicting_task_title': None,
                    'resource_type': 'Deadline',
                    'resource_name': f"Deadline: {t1['deadline'].replace('T', ' ')}",
                    'start_datetime': t1['start_datetime'],
                    'end_datetime': t1['end_datetime'],
                    'severity': 'medium'
                })

        for j in range(i + 1, num_tasks):
            t2 = tasks[j]
            
            # Check overlap
            if check_overlap(t1['start_datetime'], t1['end_datetime'], t2['start_datetime'], t2['end_datetime']):
                # Worker overlap
                if t1['assigned_worker_id'] and t2['assigned_worker_id'] and (t1['assigned_worker_id'] == t2['assigned_worker_id']):
                    pair_key = (min(t1['id'], t2['id']), max(t1['id'], t2['id']), 'worker')
                    if pair_key not in seen_worker_pairs:
                        seen_worker_pairs.add(pair_key)
                        conflicts.append({
                            'id': f"worker-{t1['id']}-{t2['id']}",
                            'type': 'worker',
                            'title': 'Worker Double-Booking Conflict',
                            'description': f"Worker '{t1['worker_name']}' is assigned to both '{t1['title']}' ({t1['field_name']}) and '{t2['title']}' ({t2['field_name']}) during overlapping hours.",
                            'task_id': t1['id'],
                            'task_title': t1['title'],
                            'field_name': t1['field_name'],
                            'conflicting_task_id': t2['id'],
                            'conflicting_task_title': t2['title'],
                            'resource_type': 'Worker',
                            'resource_name': t1['worker_name'],
                            'start_datetime': max(t1['start_datetime'], t2['start_datetime']),
                            'end_datetime': min(t1['end_datetime'], t2['end_datetime']),
                            'severity': 'high'
                        })

                # Equipment overlap
                if t1['required_equipment_id'] and t2['required_equipment_id'] and (t1['required_equipment_id'] == t2['required_equipment_id']):
                    pair_key = (min(t1['id'], t2['id']), max(t1['id'], t2['id']), 'equipment')
                    if pair_key not in seen_equip_pairs:
                        seen_equip_pairs.add(pair_key)
                        conflicts.append({
                            'id': f"equip-{t1['id']}-{t2['id']}",
                            'type': 'equipment',
                            'title': 'Equipment Conflict',
                            'description': f"Equipment '{t1['equipment_name']}' is scheduled for both '{t1['title']}' and '{t2['title']}' simultaneously.",
                            'task_id': t1['id'],
                            'task_title': t1['title'],
                            'field_name': t1['field_name'],
                            'conflicting_task_id': t2['id'],
                            'conflicting_task_title': t2['title'],
                            'resource_type': 'Equipment',
                            'resource_name': t1['equipment_name'],
                            'start_datetime': max(t1['start_datetime'], t2['start_datetime']),
                            'end_datetime': min(t1['end_datetime'], t2['end_datetime']),
                            'severity': 'critical'
                        })

    # 2. Check Dependency Conflicts
    dependencies = db.execute("""
        SELECT td.task_id, td.prerequisite_task_id,
               t.title AS task_title, t.start_datetime AS task_start, t.end_datetime AS task_end,
               t.status AS task_status, f.field_name,
               p.title AS prereq_title, p.start_datetime AS prereq_start, p.end_datetime AS prereq_end,
               p.status AS prereq_status
        FROM task_dependencies td
        JOIN tasks t ON td.task_id = t.id
        JOIN fields f ON t.field_id = f.id
        JOIN tasks p ON td.prerequisite_task_id = p.id
        WHERE t.user_id = ? AND t.status NOT IN ('Completed', 'Cancelled')
    """, (user_id,)).fetchall()

    for dep in dependencies:
        task_start = parse_iso(dep['task_start'])
        prereq_end = parse_iso(dep['prereq_end'])
        
        # Timing violation: dependent task is scheduled before prerequisite finishes
        if task_start and prereq_end and task_start < prereq_end:
            conflicts.append({
                'id': f"dep-time-{dep['task_id']}-{dep['prerequisite_task_id']}",
                'type': 'dependency',
                'title': 'Dependency Timing Conflict',
                'description': f"Task '{dep['task_title']}' is scheduled to start before prerequisite '{dep['prereq_title']}' ends ({dep['prereq_end'].replace('T', ' ')}).",
                'task_id': dep['task_id'],
                'task_title': dep['task_title'],
                'field_name': dep['field_name'],
                'conflicting_task_id': dep['prerequisite_task_id'],
                'conflicting_task_title': dep['prereq_title'],
                'resource_type': 'Prerequisite Task',
                'resource_name': dep['prereq_title'],
                'start_datetime': dep['task_start'],
                'end_datetime': dep['task_end'],
                'severity': 'critical'
            })
        elif dep['task_status'] == 'In Progress' and dep['prereq_status'] != 'Completed':
            conflicts.append({
                'id': f"dep-status-{dep['task_id']}-{dep['prerequisite_task_id']}",
                'type': 'dependency',
                'title': 'Dependency Incomplete Violation',
                'description': f"Task '{dep['task_title']}' was marked In Progress while prerequisite '{dep['prereq_title']}' is still {dep['prereq_status']}.",
                'task_id': dep['task_id'],
                'task_title': dep['task_title'],
                'field_name': dep['field_name'],
                'conflicting_task_id': dep['prerequisite_task_id'],
                'conflicting_task_title': dep['prereq_title'],
                'resource_type': 'Prerequisite Task',
                'resource_name': dep['prereq_title'],
                'start_datetime': dep['task_start'],
                'end_datetime': dep['task_end'],
                'severity': 'high'
            })

    return conflicts

def validate_task_dates(start_datetime, end_datetime, deadline=None):
    """
    Validate date inputs. Returns (is_valid: bool, error_msg: str).
    """
    s = parse_iso(start_datetime)
    e = parse_iso(end_datetime)
    if not s or not e:
        return False, "Invalid start or end date/time format."
    if e <= s:
        return False, "End date and time must be strictly after start date and time."
    if deadline:
        d = parse_iso(deadline)
        if not d:
            return False, "Invalid deadline date/time format."
    return True, None
