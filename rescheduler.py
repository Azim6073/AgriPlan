from datetime import datetime, timedelta
from database import get_db
from conflict_detector import parse_iso, check_overlap

def get_task_reschedule_suggestions(task_id, user_id, db=None, max_suggestions=4):
    """
    Rule-based alternative time slot finder.
    Calculates non-overlapping slots respecting worker, equipment, and prerequisites.
    """
    if db is None:
        db = get_db()
        
    task = db.execute("""
        SELECT t.*, f.field_name, 
               w.worker_name, 
               e.equipment_name
        FROM tasks t
        JOIN fields f ON t.field_id = f.id
        LEFT JOIN workers w ON t.assigned_worker_id = w.id
        LEFT JOIN equipment e ON t.required_equipment_id = e.id
        WHERE t.id = ? AND t.user_id = ?
    """, (task_id, user_id)).fetchone()
    
    if not task:
        return {'success': False, 'message': 'Task not found'}
        
    start_dt = parse_iso(task['start_datetime'])
    end_dt = parse_iso(task['end_datetime'])
    if not start_dt or not end_dt or end_dt <= start_dt:
        duration = timedelta(hours=2) # fallback
    else:
        duration = end_dt - start_dt
        
    deadline_dt = parse_iso(task['deadline']) if task['deadline'] else None
    
    # 1. Determine earliest possible start time
    # Must be after now, and after all prerequisite tasks finish
    now_dt = datetime.now()
    earliest_start = max(start_dt, now_dt)
    
    prereqs = db.execute("""
        SELECT t.id, t.title, t.end_datetime, t.status
        FROM task_dependencies td
        JOIN tasks t ON td.prerequisite_task_id = t.id
        WHERE td.task_id = ?
    """, (task_id,)).fetchall()
    
    for p in prereqs:
        p_end = parse_iso(p['end_datetime'])
        if p_end and p_end > earliest_start:
            earliest_start = p_end

    # 2. Collect busy intervals for assigned worker & required equipment
    worker_id = task['assigned_worker_id']
    equip_id = task['required_equipment_id']
    
    busy_intervals = []
    
    # Other tasks using the same worker
    if worker_id:
        worker_tasks = db.execute("""
            SELECT id, title, start_datetime, end_datetime 
            FROM tasks
            WHERE user_id = ? AND assigned_worker_id = ? 
              AND id != ? AND status NOT IN ('Completed', 'Cancelled')
        """, (user_id, worker_id, task_id)).fetchall()
        for wt in worker_tasks:
            ws = parse_iso(wt['start_datetime'])
            we = parse_iso(wt['end_datetime'])
            if ws and we:
                busy_intervals.append((ws, we, f"Worker {task['worker_name']} busy on '{wt['title']}'"))
                
    # Other tasks using the same equipment
    if equip_id:
        equip_tasks = db.execute("""
            SELECT id, title, start_datetime, end_datetime 
            FROM tasks
            WHERE user_id = ? AND required_equipment_id = ? 
              AND id != ? AND status NOT IN ('Completed', 'Cancelled')
        """, (user_id, equip_id, task_id)).fetchall()
        for et in equip_tasks:
            es = parse_iso(et['start_datetime'])
            ee = parse_iso(et['end_datetime'])
            if es and ee:
                busy_intervals.append((es, ee, f"Equipment {task['equipment_name']} busy on '{et['title']}'"))

    # Helper: is candidate window [cand_start, cand_end] free of resource conflicts?
    def is_slot_free(cand_start, cand_end):
        for b_start, b_end, reason in busy_intervals:
            if (cand_start < b_end) and (b_start < cand_end):
                return False, reason
        return True, "All resources available"

    # Search window: starting from earliest_start, probe candidate slots
    suggestions = []
    
    # Candidate starting search: round up to nearest half hour
    search_cursor = earliest_start
    if search_cursor.minute not in (0, 30):
        if search_cursor.minute < 30:
            search_cursor = search_cursor.replace(minute=30, second=0, microsecond=0)
        else:
            search_cursor = (search_cursor + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            
    # Probe candidate times forward for up to 7 days
    max_days = 7
    step = timedelta(minutes=60) # 1 hour search step
    end_search_limit = search_cursor + timedelta(days=max_days)
    
    while search_cursor < end_search_limit and len(suggestions) < max_suggestions:
        # Farm work hours: prefer daytime between 07:00 and 19:00
        hour = search_cursor.hour
        if hour < 7:
            search_cursor = search_cursor.replace(hour=7, minute=0)
            continue
        elif hour >= 18: # If past 18:00, jump to next day 08:00
            search_cursor = (search_cursor + timedelta(days=1)).replace(hour=8, minute=0)
            continue
            
        cand_end = search_cursor + duration
        if cand_end.hour > 19: # Doesn't finish within daytime work hours
            search_cursor = (search_cursor + timedelta(days=1)).replace(hour=8, minute=0)
            continue
            
        # Check resource availability
        free, reason = is_slot_free(search_cursor, cand_end)
        
        # Check against current task's conflicting original time
        is_same_as_original = (search_cursor == start_dt)
        
        if free and not is_same_as_original:
            cand_start_str = search_cursor.strftime("%Y-%m-%dT%H:%M")
            cand_end_str = cand_end.strftime("%Y-%m-%dT%H:%M")
            
            # Format explanation
            rationale_parts = []
            if task['worker_name']:
                rationale_parts.append(f"{task['worker_name']} is available")
            if task['equipment_name']:
                rationale_parts.append(f"{task['equipment_name']} is ready")
            if prereqs:
                rationale_parts.append("Prerequisites satisfied")
                
            meets_deadline = True
            if deadline_dt:
                if cand_end <= deadline_dt:
                    diff_hours = round((deadline_dt - cand_end).total_seconds() / 3600, 1)
                    rationale_parts.append(f"Finishes {diff_hours}h before deadline")
                else:
                    meets_deadline = False
                    over_hours = round((cand_end - deadline_dt).total_seconds() / 3600, 1)
                    rationale_parts.append(f"Caution: Exceeds deadline by {over_hours}h")

            rationale = " • ".join(rationale_parts) if rationale_parts else "Time slot is completely clear."
            
            suggestions.append({
                'start_datetime': cand_start_str,
                'end_datetime': cand_end_str,
                'duration_minutes': int(duration.total_seconds() // 60),
                'display_start': search_cursor.strftime("%b %d, %Y at %I:%M %p"),
                'display_end': cand_end.strftime("%I:%M %p"),
                'meets_deadline': meets_deadline,
                'rationale': rationale
            })
            
            # Jump forward by at least duration or 2 hours for diverse alternative options
            jump = max(duration, timedelta(hours=2))
            search_cursor += jump
        else:
            search_cursor += step

    return {
        'success': True,
        'task': dict(task),
        'duration_str': f"{int(duration.total_seconds() // 3600)}h {int((duration.total_seconds() % 3600) // 60)}m",
        'suggestions': suggestions
    }

def apply_reschedule(task_id, new_start, new_end, user_id, db=None):
    """
    Applies user-confirmed rescheduling to a task.
    Updates start_datetime, end_datetime, updated_at and adds a notification.
    """
    if db is None:
        db = get_db()
        
    # Verify task ownership
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)).fetchone()
    if not task:
        return {'success': False, 'message': 'Task not found or access denied'}
        
    s = parse_iso(new_start)
    e = parse_iso(new_end)
    if not s or not e or e <= s:
        return {'success': False, 'message': 'Invalid start or end date/time'}
        
    start_str = s.strftime("%Y-%m-%dT%H:%M")
    end_str = e.strftime("%Y-%m-%dT%H:%M")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    db.execute("""
        UPDATE tasks 
        SET start_datetime = ?, end_datetime = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
    """, (start_str, end_str, now_str, task_id, user_id))
    
    # Add in-app notification
    notification_msg = f"Task '{task['title']}' was successfully rescheduled to {s.strftime('%b %d, %Y %I:%M %p')} - {e.strftime('%I:%M %p')}."
    db.execute("""
        INSERT INTO notifications (user_id, message, notification_type, task_id)
        VALUES (?, ?, 'success', ?)
    """, (user_id, notification_msg, task_id))
    
    db.commit()
    
    return {
        'success': True,
        'message': f"Task '{task['title']}' rescheduled successfully!",
        'new_start': start_str,
        'new_end': end_str
    }
