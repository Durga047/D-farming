
import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Set SECRET_KEY as an environment variable before production use.
app.secret_key = os.environ.get(
    "SECRET_KEY", "dev-only-change-this-secret"
)

# Always use the database located beside this app.py file.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create missing tables and safely add missing user columns."""
    conn = get_db_connection()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                password TEXT
            )
        """)

        # Add new profile fields without deleting existing user data.
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }

        new_columns = {
            "phone": "TEXT",
            "address": "TEXT",
            "occupation": "TEXT",
        }

        for column, data_type in new_columns.items():
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {data_type}"
                )

        # Preserve the existing project tables.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_name TEXT,
                description TEXT,
                price REAL,
                image TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plant_id INTEGER,
                quantity INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS plantation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                location TEXT,
                date TEXT,
                plant_count INTEGER
            )
        """)

        # Prevent duplicate email addresses for new registrations.
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
            ON users(email COLLATE NOCASE)
            WHERE email IS NOT NULL AND email != ''
        """)

        conn.commit()
    finally:
        conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    """Basic health endpoint for future monitoring."""
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return jsonify(status="ok", database="connected"), 200
    except sqlite3.Error:
        app.logger.exception("Database health check failed")
        return jsonify(status="error", database="unavailable"), 503


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register_updated.html")

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    occupation = request.form.get("occupation", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([first_name, last_name, email, phone, address, occupation]):
        flash("Please complete all required fields.", "error")
        return redirect(url_for("register"))

    if len(phone) != 10 or not phone.isdigit():
        flash("Enter a valid 10-digit phone number.", "error")
        return redirect(url_for("register"))

    if len(password) < 6:
        flash("Password must contain at least 6 characters.", "error")
        return redirect(url_for("register"))

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("register"))

    name = f"{first_name} {last_name}"
    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()

        if existing:
            flash("An account with this email already exists.", "error")
            return redirect(url_for("register"))

        conn.execute("""
            INSERT INTO users
                (name, email, password, phone, address, occupation)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            password_hash,
            phone,
            address,
            occupation,
        ))
        conn.commit()

    except sqlite3.Error:
        app.logger.exception("Registration database error")
        flash("Registration could not be completed. Please try again.", "error")
        return redirect(url_for("register"))
    finally:
        conn.close()

    flash("Registration successful. Please log in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Enter both email and password.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT id, name, email, password FROM users "
            "WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
    finally:
        conn.close()

    if user and check_password_hash(user["password"], password):
        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        flash("Login successful.", "success")
        return redirect(url_for("home"))

    flash("Invalid email or password.", "error")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/vip-register", methods=["GET", "POST"])
def vip_register():
    if request.method == "POST":
        # VIP database saving is not implemented yet.
        # Keep this route until we add the VIP database design.
        flash(
            "VIP registration is not connected to the database yet.",
            "error",
        )
        return redirect(url_for("vip_register"))

    return render_template("vip_register.html")


# Initialize the database when the application starts.
init_db()


if __name__ == "__main__":
    app.run(debug=True)