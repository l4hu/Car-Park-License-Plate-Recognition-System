#!/usr/bin/python3
"""
Smart Car Park System - Web Interface

Provides a web interface to manage registered license plates:
- Add new license plates
- Remove existing license plates
- View all registered license plates
- View entry/exit logs
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
import logging
import functools
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_app.log"),
        logging.StreamHandler()
    ]
)

# Configuration
db_path = "car_park.db"
app = Flask(__name__)
app.secret_key = os.urandom(24)  # For flash messages and session

# Default admin credentials - in a real system, use a more secure approach
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

# Add context processor to provide 'now' to all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Login decorator
def login_required(func):
    @functools.wraps(func)
    def secure_function(*args, **kwargs):
        if "logged_in" not in session:
            flash("Please log in to access this page", "danger")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return secure_function


@app.route("/")
def index():
    """Home page - redirects to login if not logged in, otherwise to dashboard"""
    if "logged_in" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Simple authentication - replace with a more secure approach in production
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            flash("Login successful", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Logout and redirect to login page"""
    session.pop("logged_in", None)
    flash("You have been logged out", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard showing system status"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get total registered plates
        cursor.execute("SELECT COUNT(*) as count FROM plates")
        plate_count = cursor.fetchone()["count"]
        
        # Get recent entries
        cursor.execute("""
            SELECT plate_number, action, timestamp 
            FROM movement_log 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        recent_activity = cursor.fetchall()
        
        conn.close()
        
        return render_template(
            "dashboard.html", 
            plate_count=plate_count,
            recent_activity=recent_activity
        )
    
    except Exception as e:
        logging.error(f"Dashboard error: {str(e)}")
        flash("Error loading dashboard", "danger")
        return render_template("dashboard.html", error=True)


@app.route("/plates")
@login_required
def list_plates():
    """List all registered license plates"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, plate_number, added_date FROM plates ORDER BY added_date DESC")
        plates = cursor.fetchall()
        
        conn.close()
        
        return render_template("plates.html", plates=plates)
    
    except Exception as e:
        logging.error(f"Error listing plates: {str(e)}")
        flash("Error retrieving plate data", "danger")
        return render_template("plates.html", plates=[])


@app.route("/plates/add", methods=["GET", "POST"])
@login_required
def add_plate():
    """Add a new license plate to the system"""
    if request.method == "POST":
        plate_number = request.form.get("plate_number", "").strip().upper()
        
        if not plate_number:
            flash("License plate number cannot be empty", "danger")
            return redirect(url_for("add_plate"))
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if plate already exists
            cursor.execute("SELECT 1 FROM plates WHERE plate_number = ?", (plate_number,))
            if cursor.fetchone():
                flash(f"License plate {plate_number} is already registered", "warning")
                conn.close()
                return redirect(url_for("list_plates"))
            
            # Add new plate
            cursor.execute(
                "INSERT INTO plates (plate_number) VALUES (?)",
                (plate_number,)
            )
            
            conn.commit()
            conn.close()
            
            flash(f"License plate {plate_number} added successfully", "success")
            return redirect(url_for("list_plates"))
        
        except Exception as e:
            logging.error(f"Error adding plate: {str(e)}")
            flash("Error adding license plate", "danger")
            return redirect(url_for("add_plate"))
    
    return render_template("add_plate.html")


@app.route("/plates/remove/<int:plate_id>", methods=["POST"])
@login_required
def remove_plate(plate_id):
    """Remove a license plate from the system"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the plate number for the confirmation message
        cursor.execute("SELECT plate_number FROM plates WHERE id = ?", (plate_id,))
        result = cursor.fetchone()
        
        if result:
            plate_number = result[0]
            
            # Delete the plate
            cursor.execute("DELETE FROM plates WHERE id = ?", (plate_id,))
            conn.commit()
            
            flash(f"License plate {plate_number} removed successfully", "success")
        else:
            flash("License plate not found", "danger")
        
        conn.close()
        
    except Exception as e:
        logging.error(f"Error removing plate: {str(e)}")
        flash("Error removing license plate", "danger")
    
    return redirect(url_for("list_plates"))


@app.route("/logs")
@login_required
def view_logs():
    """View vehicle movement logs"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, plate_number, action, timestamp 
            FROM movement_log 
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        logs = cursor.fetchall()
        
        conn.close()
        
        return render_template("logs.html", logs=logs)
    
    except Exception as e:
        logging.error(f"Error viewing logs: {str(e)}")
        flash("Error retrieving log data", "danger")
        return render_template("logs.html", logs=[])


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logging.error(f"Server error: {str(e)}")
    return render_template("500.html"), 500


if __name__ == "__main__":
    # Ensure database exists
    if not os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create plates table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS plates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT UNIQUE NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS movement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            conn.commit()
            conn.close()
            logging.info("Database initialized")
            
        except Exception as e:
            logging.error(f"Failed to initialize database: {str(e)}")
    
    # Run the Flask application
    app.run(host="0.0.0.0", port=5000, debug=True)