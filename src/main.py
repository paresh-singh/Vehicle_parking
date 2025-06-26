import os
import sys
from datetime import timedelta

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from werkzeug.security import generate_password_hash # For admin password
from dotenv import load_dotenv

from src.extensions import db, jwt # Import db and jwt from extensions

load_dotenv() # Load environment variables from .env file

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "a_default_secret_key_for_development_12345")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///vehicle_parking.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # JWT Configuration
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "a_default_jwt_secret_key_12345") # Change this in production!
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]

    db.init_app(app)
    jwt.init_app(app)

    # This import is now safe here because db is initialized above
    from src.models.models import User, ParkingLot, ParkingSpot, Reservation
    from src.routes.auth import auth_bp
    from src.routes.admin import admin_bp
    from src.routes.user_routes import user_routes_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(user_routes_bp, url_prefix="/api/user")

    with app.app_context():
        # Create database tables if they don"t exist
        # This check ensures it runs only once per app start or when needed
        if not app.config.get("_database_initialized", False):
            db.create_all()
            admin_username = os.getenv("ADMIN_USERNAME", "admin")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
            admin_user = User.query.filter_by(username=admin_username).first()
            if not admin_user:
                hashed_password = generate_password_hash(admin_password)
                new_admin = User(username=admin_username, password_hash=hashed_password, role="admin")
                db.session.add(new_admin)
                db.session.commit()
                print(f"Admin user \'{admin_username}\' created.")
            else:
                print(f"Admin user \'{admin_username}\' already exists.")
            app.config["_database_initialized"] = True

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve(path):
        static_folder_path = app.static_folder
        if static_folder_path is None:
            return "Static folder not configured", 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, "login.html")
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, "login.html")
            else:
                return "Flask backend is running. No index.html found in static folder. To access API, use /auth or /api/...", 200
    
    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

