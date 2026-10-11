import sqlite3
import os

def get_db(custom_path=None):
    """Get SQLite database connection for current request context, custom path, or standalone script."""
    if custom_path:
        conn = sqlite3.connect(custom_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    try:
        from flask import g, current_app
        if 'db' not in g:
            db_path = current_app.config['DATABASE']
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db
    except (RuntimeError, ImportError):
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'agriplan.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def close_db(e=None):
    """Close the database connection at the end of the request."""
    try:
        from flask import g
        db = g.pop('db', None)
        if db is not None:
            db.close()
    except (RuntimeError, ImportError):
        pass

def init_db(db_conn=None, db_path=None):
    """Initialize database tables with schema."""
    if db_conn is not None:
        conn = db_conn
        close_after = False
    elif db_path:
        conn = get_db(db_path)
        close_after = True
    else:
        conn = get_db()
        close_after = False
    
    schema = """
    -- Users Table
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Fields Table
    CREATE TABLE IF NOT EXISTS fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        field_name TEXT NOT NULL,
        location TEXT,
        size REAL NOT NULL CHECK(size > 0),
        area_unit TEXT DEFAULT 'acres',
        soil_type TEXT,
        irrigation_type TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- Crops Table
    CREATE TABLE IF NOT EXISTS crops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        field_id INTEGER NOT NULL,
        crop_name TEXT NOT NULL,
        variety TEXT,
        sowing_date DATE NOT NULL,
        expected_harvest_date DATE NOT NULL,
        status TEXT DEFAULT 'Growing',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
    );

    -- Workers Table
    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        worker_name TEXT NOT NULL,
        contact TEXT,
        skills TEXT,
        availability_status TEXT DEFAULT 'Available',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- Equipment Table
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        equipment_name TEXT NOT NULL,
        equipment_type TEXT NOT NULL,
        identification_number TEXT,
        availability_status TEXT DEFAULT 'Available',
        maintenance_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- Tasks Table
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        field_id INTEGER NOT NULL,
        crop_id INTEGER,
        title TEXT NOT NULL,
        task_type TEXT NOT NULL,
        description TEXT,
        start_datetime TEXT NOT NULL,
        end_datetime TEXT NOT NULL,
        deadline TEXT,
        priority TEXT DEFAULT 'Medium',
        assigned_worker_id INTEGER,
        required_equipment_id INTEGER,
        status TEXT DEFAULT 'Pending',
        completion_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE,
        FOREIGN KEY (crop_id) REFERENCES crops(id) ON DELETE SET NULL,
        FOREIGN KEY (assigned_worker_id) REFERENCES workers(id) ON DELETE SET NULL,
        FOREIGN KEY (required_equipment_id) REFERENCES equipment(id) ON DELETE SET NULL
    );

    -- Task Dependencies Table
    CREATE TABLE IF NOT EXISTS task_dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        prerequisite_task_id INTEGER NOT NULL,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
        FOREIGN KEY (prerequisite_task_id) REFERENCES tasks(id) ON DELETE CASCADE,
        UNIQUE(task_id, prerequisite_task_id)
    );

    -- Notifications Table
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        notification_type TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        task_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
    );

    -- Indexes for high performance
    CREATE INDEX IF NOT EXISTS idx_fields_user ON fields(user_id);
    CREATE INDEX IF NOT EXISTS idx_crops_user ON crops(user_id);
    CREATE INDEX IF NOT EXISTS idx_crops_field ON crops(field_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_field ON tasks(field_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_worker ON tasks(assigned_worker_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_equip ON tasks(required_equipment_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
    """
    conn.executescript(schema)
    conn.commit()
    if close_after:
        conn.close()
