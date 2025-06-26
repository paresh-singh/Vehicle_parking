from functools import wraps
from flask import jsonify, request # Added request for debugging
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, get_jwt

def roles_required(*roles):
    """Decorator to ensure user has one of the specified roles."""
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            print(f"DEBUG: roles_required - Incoming Headers: {request.headers}") # DEBUG
            try:
                verify_jwt_in_request()
                jwt_payload = get_jwt()
                user_role = jwt_payload.get("role")
                print(f"DEBUG: roles_required - JWT Payload Role: {user_role}") # DEBUG
                if user_role not in roles:
                    print(f"DEBUG: roles_required - Role mismatch: {user_role} not in {roles}") # DEBUG
                    roles_display_string = ", ".join(roles)
                    return jsonify(message=f"Access restricted: User does not have required role(s) ({roles_display_string})."), 403
            except Exception as e:
                print(f"DEBUG: roles_required - Exception during JWT verification: {e}") # DEBUG
                return jsonify(message="Token verification failed."), 401 # Or handle specific JWT errors
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def admin_required(fn):
    """Decorator to ensure user has admin role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        print(f"DEBUG: admin_required - Incoming Headers: {request.headers}") # DEBUG
        try:
            verify_jwt_in_request()
            jwt_payload = get_jwt() # Get full payload
            user_role = jwt_payload.get("role") # Get role from the main payload
            print(f"DEBUG: admin_required - JWT Full Payload: {jwt_payload}") # DEBUG
            print(f"DEBUG: admin_required - Extracted Role: {user_role}") # DEBUG
            if user_role != "admin":
                print(f"DEBUG: admin_required - Role mismatch: {user_role} is not admin") # DEBUG
                return jsonify(message="Admins only!"), 403
        except Exception as e:
            print(f"DEBUG: admin_required - Exception during JWT verification: {e}") # DEBUG
            return jsonify(message=f"Admin token verification failed: {str(e)}"), 401
        return fn(*args, **kwargs)
    return wrapper

def user_required(fn):
    """Decorator to ensure user has user role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        print(f"DEBUG: user_required - Incoming Headers: {request.headers}") # DEBUG
        try:
            verify_jwt_in_request()
            jwt_payload = get_jwt() # Get full payload
            user_role = jwt_payload.get("role") # Get role from the main payload
            print(f"DEBUG: user_required - JWT Full Payload: {jwt_payload}") # DEBUG
            print(f"DEBUG: user_required - Extracted Role: {user_role}") # DEBUG
            if user_role != "user":
                print(f"DEBUG: user_required - Role mismatch: {user_role} is not user") # DEBUG
                return jsonify(message="Users only!"), 403
        except Exception as e:
            print(f"DEBUG: user_required - Exception during JWT verification: {e}") # DEBUG
            return jsonify(message="User token verification failed."), 401
        return fn(*args, **kwargs)
    return wrapper

