
import os
import math
import sqlite3
import uuid

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
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


# --------------------------------------------------
# 1. APPLICATION CONFIGURATION
# --------------------------------------------------

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-only-change-this-secret"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.environ.get(
    "DATABASE_PATH",
    os.path.join(BASE_DIR, "database.db")
)

UPLOAD_FOLDER = os.environ.get(
    "UPLOAD_FOLDER",
    os.path.join(BASE_DIR, "static", "uploads")
)

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".avif"
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


# --------------------------------------------------
# 2. DATABASE CONNECTION
# --------------------------------------------------

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------
# 3. DATABASE INITIALIZATION AND SAFE MIGRATION
# --------------------------------------------------

def init_db():
    conn = get_db_connection()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                occupation TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 0
            )
        """)

        user_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        for column in ("phone", "address", "occupation"):
            if column not in user_columns:
                conn.execute(
                    f"ALTER TABLE users ADD COLUMN {column} TEXT"
                )

        # Migrate older databases without recreating them.
        password_flag_added = (
            "must_change_password" not in user_columns
        )

        if password_flag_added:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN must_change_password
                INTEGER NOT NULL DEFAULT 0
            """)

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
            ON users(email COLLATE NOCASE)
            WHERE email IS NOT NULL AND email != ''
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_name TEXT,
                description TEXT,
                image TEXT,
                price REAL
            )
        """)

        # Safely migrate plants table to support plant_name.
        plant_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(plants)"
            ).fetchall()
        }

        if "plant_name" not in plant_columns:
            if "name" not in plant_columns:
                raise sqlite3.OperationalError(
                    "Plants table has no name column"
                )

            conn.execute(
                "ALTER TABLE plants ADD COLUMN plant_name TEXT"
            )
            conn.execute("""
                UPDATE plants
                SET plant_name = name
                WHERE plant_name IS NULL
                   OR TRIM(plant_name) = ''
            """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plant_id INTEGER,
                quantity INTEGER,
                booking_date TEXT,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (plant_id) REFERENCES plants(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS plantation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plant_name TEXT,
                tree_count INTEGER,
                location TEXT,
                plantation_date TEXT,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS vip_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                customer_photo TEXT,
                land_name TEXT,
                land_area REAL,
                land_unit TEXT DEFAULT 'acre',
                land_description TEXT,
                land_photo TEXT,
                city TEXT NOT NULL,
                district TEXT NOT NULL,
                state TEXT NOT NULL,
                pincode TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                plant_name TEXT NOT NULL,
                tree_count INTEGER NOT NULL CHECK (tree_count >= 1),
                plant_photo TEXT NOT NULL,
                plantation_date TEXT,
                plant_notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
        """)

        # Existing VIP users in an older database get a one-time
        # password-change requirement during this migration.
        if password_flag_added:
            conn.execute("""
                UPDATE users
                SET must_change_password = 1
                WHERE id IN (
                    SELECT user_id FROM vip_registrations
                )
            """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# --------------------------------------------------
# 4. HOME PAGE
# --------------------------------------------------



@app.route("/")
def home():
    conn = None

    try:
        conn = get_db_connection()

        plants = conn.execute("""
            SELECT id, plant_name, description, image, price
            FROM plants
            ORDER BY id DESC
        """).fetchall()

        return render_template("index.html", plants=plants)

    except sqlite3.Error:
        app.logger.exception("Failed to load plants")
        return render_template("index.html", plants=[])

    finally:
        if conn is not None:
            conn.close()



# --------------------------------------------------
# ADD PLANT
# --------------------------------------------------
@app.route("/addplant", methods=["GET", "POST"])
def add_plant():
    if request.method == "POST":
        name = request.form.get("plant_name", "").strip()
        description = request.form.get("description", "").strip()
        price_text = request.form.get("price", "").strip()

        if not name or not price_text:
            flash("Plant name and price are required.")
            return redirect(url_for("add_plant"))

        try:
            price = float(price_text)

            if not math.isfinite(price) or price < 0:
                raise ValueError

        except ValueError:
            flash("Please enter a valid, non-negative price.")
            return redirect(url_for("add_plant"))

        image_filename = None
        image_path = None
        conn = None

        try:
            # Save the uploaded image.
            image_filename, image_path = save_uploaded_image(
                "plant_photo",
                required=True
            )

            conn = get_db_connection()

            # Use the actual column name from your database.
            conn.execute("""
                INSERT INTO plants
                    (plant_name, description, image, price)
                VALUES (?, ?, ?, ?)
            """, (
                name,
                description,
                image_filename,
                price
            ))

            conn.commit()

            flash("Plant and image added successfully.")
            return redirect(url_for("home"))

        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("add_plant"))

        except sqlite3.Error:
            app.logger.exception("Failed to add plant")

            if conn is not None:
                conn.rollback()

            # Remove only the new upload if the database save fails.
            if image_path:
                try:
                    os.remove(image_path)
                except OSError:
                    app.logger.warning(
                        "Could not remove failed upload: %s",
                        image_filename
                    )

            flash("Unable to save the plant. Please try again.")
            return redirect(url_for("add_plant"))

        finally:
            if conn is not None:
                conn.close()

    return render_template("add_plant.html")

# --------------------------------------------------
# 5. HEALTH CHECK
# --------------------------------------------------

@app.route("/health")
def health():
    conn = None

    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()

        return jsonify({
            "status": "ok",
            "application": "D-Farming",
            "database": "connected"
        }), 200

    except sqlite3.Error:
        app.logger.exception("Health check database failure")
        return jsonify({
            "status": "error",
            "database": "unavailable"
        }), 503

    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# 6. NORMAL USER REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register_updated.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    occupation = request.form.get("occupation", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("register"))

    if len(password) < 6:
        flash("Password must contain at least 6 characters.", "error")
        return redirect(url_for("register"))

    if confirm_password and password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("register"))

    conn = get_db_connection()

    try:
        conn.execute("""
            INSERT INTO users (
                name, email, password, phone, address, occupation,
                must_change_password
            )
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (
            name,
            email,
            generate_password_hash(password),
            phone,
            address,
            occupation,
        ))

        conn.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    except sqlite3.IntegrityError:
        conn.rollback()
        flash("This email is already registered.", "error")
        return redirect(url_for("register"))

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Normal registration failed")
        flash("Registration failed. Please try again.", "error")
        return redirect(url_for("register"))

    finally:
        conn.close()


# --------------------------------------------------
# 7. LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Enter your email and password.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()

    try:
        user = conn.execute("""
            SELECT id, name, email, password, must_change_password
            FROM users
            WHERE email = ? COLLATE NOCASE
        """, (email,)).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(
        user["password"], password
    ):
        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]

    # VIP users who must change their password go to that page first.
    if user["must_change_password"]:
        session["must_change_password"] = True
        flash("Please change your password to continue.", "info")
        return redirect(url_for("change_password"))

    flash("Login successful.", "success")
    return redirect(url_for("home"))


# --------------------------------------------------
# 8. CHANGE PASSWORD
# --------------------------------------------------

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("change_password.html")

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    conn = get_db_connection()

    try:
        user = conn.execute("""
            SELECT password
            FROM users
            WHERE id = ?
        """, (session["user_id"],)).fetchone()

        if user is None or not check_password_hash(
            user["password"], current_password
        ):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("change_password"))

        if len(new_password) < 8:
            flash(
                "New password must contain at least 8 characters.",
                "error"
            )
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return redirect(url_for("change_password"))

        conn.execute("""
            UPDATE users
            SET password = ?, must_change_password = 0
            WHERE id = ?
        """, (
            generate_password_hash(new_password),
            session["user_id"]
        ))

        conn.commit()

        session.pop("must_change_password", None)
        flash("Password changed successfully.", "success")
        return redirect(url_for("home"))

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Password change failed")
        flash("Could not change the password. Please try again.", "error")
        return redirect(url_for("change_password"))

    finally:
        conn.close()


# --------------------------------------------------
# 9. LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# --------------------------------------------------
# 10. SAVE UPLOADED IMAGES
# --------------------------------------------------

def save_uploaded_image(field_name, required=False):
    uploaded = request.files.get(field_name)

    if not uploaded or not uploaded.filename:
        if required:
            raise ValueError(
                f"Please upload the {field_name.replace('_', ' ')}."
            )
        return None, None

    safe_name = secure_filename(uploaded.filename)
    extension = os.path.splitext(safe_name)[1].lower()

    if not safe_name or extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            "Unsupported image format. Use JPG, JPEG, PNG, WEBP, or AVIF."
        )

    filename = f"{uuid.uuid4().hex}{extension}"
    full_path = os.path.join(UPLOAD_FOLDER, filename)
    uploaded.save(full_path)

    return filename, full_path


# --------------------------------------------------
# 11. VIP REGISTRATION
# --------------------------------------------------

@app.route("/vip-register", methods=["GET", "POST"])
def vip_register():
    if request.method == "GET":
        return render_template("vip_register.html")

    fields = {
        "first_name": request.form.get("first_name", "").strip(),
        "last_name": request.form.get("last_name", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "phone": request.form.get("phone", "").strip(),
        "occupation": request.form.get("occupation", "").strip(),
        "land_name": request.form.get("land_name", "").strip(),
        "land_description": request.form.get(
            "land_description", ""
        ).strip(),
        "land_unit": request.form.get(
            "land_unit", "acre"
        ).strip().lower(),
        "address": request.form.get("address", "").strip(),
        "city": request.form.get("city", "").strip(),
        "district": request.form.get("district", "").strip(),
        "state": request.form.get("state", "").strip(),
        "pincode": request.form.get("pincode", "").strip(),
        "plant_name": request.form.get("plant_name", "").strip(),
        "plant_notes": request.form.get("plant_notes", "").strip(),
        "plantation_date": request.form.get(
            "plantation_date", ""
        ).strip(),
        "password": request.form.get("password", ""),
        "confirm_password": request.form.get("confirm_password", ""),
    }

    required_fields = (
        "first_name", "last_name", "email", "phone", "address",
        "city", "district", "state", "pincode", "plant_name",
        "password", "confirm_password"
    )

    if any(not fields[key] for key in required_fields):
        flash("Please complete all required fields.", "error")
        return redirect(url_for("vip_register"))

    if (
        "@" not in fields["email"]
        or "." not in fields["email"].split("@")[-1]
    ):
        flash("Enter a valid email address.", "error")
        return redirect(url_for("vip_register"))

    if len(fields["phone"]) != 10 or not fields["phone"].isdigit():
        flash("Enter a valid 10-digit phone number.", "error")
        return redirect(url_for("vip_register"))

    if len(fields["pincode"]) != 6 or not fields["pincode"].isdigit():
        flash("Enter a valid 6-digit PIN code.", "error")
        return redirect(url_for("vip_register"))

    if len(fields["password"]) < 6:
        flash("Password must contain at least 6 characters.", "error")
        return redirect(url_for("vip_register"))

    if fields["password"] != fields["confirm_password"]:
        flash("Passwords do not match.", "error")
        return redirect(url_for("vip_register"))

    if fields["land_unit"] not in {"acre", "hectare", "sqft"}:
        flash("Please select a valid land area unit.", "error")
        return redirect(url_for("vip_register"))

    try:
        tree_count = int(request.form.get("tree_count", ""))
        if tree_count < 1:
            raise ValueError
    except (TypeError, ValueError):
        flash("Tree count must be a positive whole number.", "error")
        return redirect(url_for("vip_register"))

    land_area_text = request.form.get("land_area", "").strip()

    try:
        land_area = float(land_area_text) if land_area_text else None
        if land_area is not None and (
            not math.isfinite(land_area) or land_area <= 0
        ):
            raise ValueError
    except ValueError:
        flash("Land area must be a positive number.", "error")
        return redirect(url_for("vip_register"))

    def parse_coordinate(field_name, minimum, maximum):
        value = request.form.get(field_name, "").strip()
        if not value:
            return None

        number = float(value)
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise ValueError

        return number

    try:
        latitude = parse_coordinate("latitude", -90, 90)
        longitude = parse_coordinate("longitude", -180, 180)
    except ValueError:
        flash("Invalid location coordinates.", "error")
        return redirect(url_for("vip_register"))

    saved_paths = []
    conn = None

    try:
        customer_photo, path = save_uploaded_image("customer_photo")
        if path:
            saved_paths.append(path)

        land_photo, path = save_uploaded_image("land_photo")
        if path:
            saved_paths.append(path)

        plant_photo, path = save_uploaded_image(
            "plant_photo", required=True
        )
        if path:
            saved_paths.append(path)

        conn = get_db_connection()

        existing_user = conn.execute("""
            SELECT id FROM users
            WHERE email = ? COLLATE NOCASE
        """, (fields["email"],)).fetchone()

        if existing_user:
            for saved_path in saved_paths:
                if os.path.exists(saved_path):
                    os.remove(saved_path)

            flash("This email is already registered.", "error")
            return redirect(url_for("vip_register"))

        full_name = (
            f"{fields['first_name']} {fields['last_name']}"
        ).strip()

        password_hash = generate_password_hash(fields["password"])

        conn.execute("BEGIN")

        cursor = conn.execute("""
            INSERT INTO users (
                name, email, password, phone, address, occupation,
                must_change_password
            )
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (
            full_name,
            fields["email"],
            password_hash,
            fields["phone"],
            fields["address"],
            fields["occupation"],
        ))

        user_id = cursor.lastrowid

        conn.execute("""
            INSERT INTO vip_registrations (
                user_id, customer_photo, land_name, land_area,
                land_unit, land_description, land_photo, city,
                district, state, pincode, latitude, longitude,
                plant_name, tree_count, plant_photo,
                plantation_date, plant_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            customer_photo,
            fields["land_name"] or None,
            land_area,
            fields["land_unit"],
            fields["land_description"] or None,
            land_photo,
            fields["city"],
            fields["district"],
            fields["state"],
            fields["pincode"],
            latitude,
            longitude,
            fields["plant_name"],
            tree_count,
            plant_photo,
            fields["plantation_date"] or None,
            fields["plant_notes"] or None,
        ))

        conn.commit()

        flash(
            "VIP registration successful. Please log in.",
            "success"
        )
        return redirect(url_for("login"))

    except ValueError as error:
        if conn is not None:
            conn.rollback()

        for saved_path in saved_paths:
            if os.path.exists(saved_path):
                os.remove(saved_path)

        flash(str(error), "error")
        return redirect(url_for("vip_register"))

    except (sqlite3.Error, OSError):
        if conn is not None:
            conn.rollback()

        app.logger.exception("VIP registration failed")

        for saved_path in saved_paths:
            if os.path.exists(saved_path):
                os.remove(saved_path)

        flash(
            "VIP registration failed. Please check the details and try again.",
            "error"
        )
        return redirect(url_for("vip_register"))

    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# 12. START APPLICATION
# --------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )