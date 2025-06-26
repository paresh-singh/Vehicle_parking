from flask import Blueprint, request, jsonify
from src.extensions import db # Import db from extensions.py
from src.models.models import ParkingLot, ParkingSpot, User, Reservation
from src.utils.decorators import admin_required
from sqlalchemy.exc import IntegrityError

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.route("/parking_lots", methods=["POST"])
@admin_required
def create_parking_lot():
    data = request.get_json()
    required_fields = ["prime_location_name", "price", "address", "pin_code", "number_of_spots"]
    if not all(field in data for field in required_fields):
        return jsonify({"message": "Missing required fields"}), 400
    
    if not isinstance(data["number_of_spots"], int) or data["number_of_spots"] <= 0:
        return jsonify({"message": "Number of spots must be a positive integer"}), 400
    if not isinstance(data["price"], (int, float)) or data["price"] < 0:
        return jsonify({"message": "Price must be a non-negative number"}), 400

    try:
        new_lot = ParkingLot(
            prime_location_name=data["prime_location_name"],
            price=data["price"],
            address=data["address"],
            pin_code=data["pin_code"],
            number_of_spots=data["number_of_spots"]
        )
        db.session.add(new_lot)
        db.session.flush() # To get the new_lot.id for spot creation

        for i in range(1, data["number_of_spots"] + 1):
            new_spot = ParkingSpot(lot_id=new_lot.id, spot_number=i, status="A")
            db.session.add(new_spot)
        
        db.session.commit()
        return jsonify({"message": "Parking lot and spots created successfully", "lot_id": new_lot.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "An error occurred", "error": str(e)}), 500

@admin_bp.route("/parking_lots", methods=["GET"])
@admin_required
def get_parking_lots():
    lots = ParkingLot.query.all()
    output = []
    for lot in lots:
        spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        spot_details = [{
            "id": spot.id, 
            "spot_number": spot.spot_number, 
            "status": spot.status
        } for spot in spots]
        lot_data = {
            "id": lot.id,
            "prime_location_name": lot.prime_location_name,
            "price": lot.price,
            "address": lot.address,
            "pin_code": lot.pin_code,
            "number_of_spots": lot.number_of_spots,
            "available_spots": len([s for s in spot_details if s["status"] == "A"]),
            "spots": spot_details
        }
        output.append(lot_data)
    return jsonify(output), 200

@admin_bp.route("/parking_lots/<int:lot_id>", methods=["PUT"])
@admin_required
def update_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    data = request.get_json()

    if "prime_location_name" in data: lot.prime_location_name = data["prime_location_name"]
    if "price" in data: 
        if not isinstance(data["price"], (int, float)) or data["price"] < 0:
            return jsonify({"message": "Price must be a non-negative number"}), 400
        lot.price = data["price"]
    if "address" in data: lot.address = data["address"]
    if "pin_code" in data: lot.pin_code = data["pin_code"]
    
    if "number_of_spots" in data:
        new_total_spots = data["number_of_spots"]
        if not isinstance(new_total_spots, int) or new_total_spots <= 0:
            return jsonify({"message": "Number of spots must be a positive integer"}), 400

        current_spots = ParkingSpot.query.filter_by(lot_id=lot.id).order_by(ParkingSpot.spot_number).all()
        current_spot_count = len(current_spots)

        if new_total_spots > current_spot_count:
            last_spot_number = current_spots[-1].spot_number if current_spots else 0
            for i in range(current_spot_count + 1, new_total_spots + 1):
                new_spot = ParkingSpot(lot_id=lot.id, spot_number=last_spot_number + (i - current_spot_count), status="A")
                db.session.add(new_spot)
        elif new_total_spots < current_spot_count:
            spots_to_delete_count = current_spot_count - new_total_spots
            deletable_spots = [spot for spot in reversed(current_spots) if spot.status == "A"]

            if len(deletable_spots) < spots_to_delete_count:
                return jsonify({"message": f"Cannot reduce to {new_total_spots} spots. Not enough available spots to delete. Required to delete {spots_to_delete_count}, available for deletion: {len(deletable_spots)}."}), 400
            
            for i in range(spots_to_delete_count):
                db.session.delete(deletable_spots[i])
        
        lot.number_of_spots = new_total_spots

    try:
        db.session.commit()
        return jsonify({"message": "Parking lot updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "An error occurred", "error": str(e)}), 500

@admin_bp.route("/parking_lots/<int:lot_id>", methods=["DELETE"])
@admin_required
def delete_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status="O").count()
    if occupied_spots > 0:
        return jsonify({"message": "Cannot delete lot. Some parking spots are occupied."}), 400
    
    try:
        db.session.delete(lot)
        db.session.commit()
        return jsonify({"message": "Parking lot deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "An error occurred", "error": str(e)}), 500

@admin_bp.route("/parking_spots/<int:spot_id>", methods=["GET"])
@admin_required
def get_parking_spot(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    spot_data = {
        "id": spot.id,
        "lot_id": spot.lot_id,
        "spot_number": spot.spot_number,
        "status": spot.status,
        "parking_lot_name": spot.parking_lot.prime_location_name
    }
    if spot.status == "O":
        reservation = Reservation.query.filter_by(spot_id=spot.id, leaving_timestamp=None).first()
        if reservation:
            spot_data["reservation_details"] = {
                "reservation_id": reservation.id,
                "user_id": reservation.user_id,
                "username": reservation.user.username,
                "parking_timestamp": reservation.parking_timestamp.isoformat() if reservation.parking_timestamp else None
            }
    return jsonify(spot_data), 200

@admin_bp.route("/parking_spots/<int:spot_id>", methods=["DELETE"])
@admin_required
def delete_parking_spot(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    if spot.status == "O":
        return jsonify({"message": "Cannot delete spot. It is currently occupied."}), 400
    
    try:
        lot = ParkingLot.query.get(spot.lot_id)
        if lot:
            lot.number_of_spots = max(0, lot.number_of_spots - 1)
            
        db.session.delete(spot)
        db.session.commit()
        return jsonify({"message": "Parking spot deleted successfully and lot count updated."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "An error occurred", "error": str(e)}), 500

@admin_bp.route("/users", methods=["GET"])
@admin_required
def get_all_users():
    users = User.query.all()
    output = []
    for user_obj in users: # Renamed user to user_obj to avoid conflict with User model
        user_data = {"id": user_obj.id, "username": user_obj.username, "role": user_obj.role}
        output.append(user_data)
    return jsonify(output), 200

@admin_bp.route("/dashboard/summary", methods=["GET"])
@admin_required
def admin_dashboard_summary():
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    occupied_spots = ParkingSpot.query.filter_by(status="O").count()
    available_spots = total_spots - occupied_spots
    
    summary = {
        "total_parking_lots": total_lots,
        "total_parking_spots": total_spots,
        "total_occupied_spots": occupied_spots,
        "total_available_spots": available_spots,
        "occupancy_rate": (occupied_spots / total_spots * 100) if total_spots > 0 else 0
    }
    return jsonify(summary), 200

