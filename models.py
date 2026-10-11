from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

def create_user(name, email, password, db=None):
    """Register a new farmer user."""
    if db is None:
        db = get_db()
    email_clean = email.strip().lower()
    pw_hash = generate_password_hash(password)
    try:
        cursor = db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name.strip(), email_clean, pw_hash)
        )
        db.commit()
        return cursor.lastrowid, None
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            return None, "An account with this email address already exists."
        return None, f"Registration failed: {str(e)}"

def authenticate_user(email, password, db=None):
    """Authenticate user with email and password."""
    if db is None:
        db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not user:
        return None, "Invalid email or password."
    if not check_password_hash(user['password_hash'], password):
        return None, "Invalid email or password."
    return dict(user), None

def get_user_by_id(user_id, db=None):
    """Fetch user by primary key."""
    if db is None:
        db = get_db()
    user = db.execute("SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(user) if user else None
