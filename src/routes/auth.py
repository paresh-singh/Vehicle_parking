from flask import Blueprint, request, jsonify
from src.extensions import db, jwt # Import db and jwt from extensions.py
from src.models.models import User
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt

auth_bp = Blueprint("auth_bp", __name__)

# In-memory set to store revoked tokens (for a simple blacklist)
# For production, a more persistent solution like Redis would be better.
revoked_tokens = set()

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "User already exists"}), 409

    new_user = User(username=username) # Default role is user
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User created successfully"}), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        # Set identity to be the username (string) and add role to additional_claims
        additional_claims = {"role": user.role}
        access_token = create_access_token(identity=user.username, additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=user.username, additional_claims=additional_claims)
        return jsonify(access_token=access_token, refresh_token=refresh_token), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    username = get_jwt_identity()
    role = get_jwt().get("role")
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"message": "User not found for token refresh"}), 404
    additional_claims = {"role": role}
    new_access_token = create_access_token(identity=username, additional_claims=additional_claims)
    return jsonify(access_token=new_access_token), 200

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    JWT_ID = get_jwt()["jti"] # jti is "JWT ID", a unique identifier for aś JWT.
    revoked_tokens.add(JWT_ID)
    return jsonify({"message": "Successfully logged out"}), 200

# JWT error handlers are registered with the JWTManager instance (jwt from extensions.py)
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({
        "message": "The token has expired.",
        "error": "token_expired"
    }), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):  # we have to keep the argument here, Flask-JWT-Extended expects it
    return jsonify({
        "message": "Signature verification failed.",
        "error": "invalid_token"
    }), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({
        "message": "Request does not contain an access token.",
        "error": "authorization_required"
    }), 401

@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return jti in revoked_tokens

@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    return jsonify({
        "message": "The token has been revoked.",
        "error": "token_revoked"
    }), 401

