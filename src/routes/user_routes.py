from flask import Blueprint, request, jsonify, send_file, current_app
from src.extensions import db # Import db from extensions.py
from src.models.models import ParkingLot, ParkingSpot, User, Reservation
from src.utils.decorators import user_required # Assuming user_required decorator
from flask_jwt_extended import get_jwt_identity
import datetime
import io
import csv

user_routes_bp = Blueprint("user_routes_bp", __name__)

@user_routes_bp.route("/parking_lots", methods=["GET"])
@user_required
def get_available_parking_lots():
    lots = ParkingLot.query.all()
    output = []
    for lot in lots:
        available_spots_count = ParkingSpot.query.filter_by(lot_id=lot.id, status="A").count()
        if available_spots_count > 0: # Only show lots with available spots
            lot_data = {
                "id": lot.id,
                "prime_location_name": lot.prime_location_name,
                "price_per_hour": lot.price, # Assuming price is per hour, clarify if different
                "address": lot.address,
                "pin_code": lot.pin_code,
                "available_spots": available_spots_count,
                "total_spots": lot.number_of_spots
            }
            output.append(lot_data)
    return jsonify(output), 200

@user_routes_bp.route("/reservations", methods=["POST"])
@user_required
def book_parking_spot():
    data = request.get_json()
    lot_id = data.get("lot_id")
    if not lot_id:
        return jsonify({"message": "lot_id is required"}), 400

    current_user_username = get_jwt_identity() # This is now a string (username)
    user = User.query.filter_by(username=current_user_username).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    available_spot = ParkingSpot.query.filter_by(lot_id=lot_id, status="A").order_by(ParkingSpot.spot_number).first()

    if not available_spot:
        return jsonify({"message": "No available parking spots in this lot"}), 404

    try:
        new_reservation = Reservation(
            spot_id=available_spot.id,
            user_id=user.id
        )
        db.session.add(new_reservation)
        db.session.commit()
        return jsonify({"message": "Parking spot reserved. Please proceed to park and confirm.", 
                        "reservation_id": new_reservation.id, 
                        "spot_id": available_spot.id,
                        "spot_number": available_spot.spot_number,
                        "lot_id": lot_id
                        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating reservation: {e}")
        return jsonify({"message": "Error creating reservation", "error": str(e)}), 500

@user_routes_bp.route("/reservations/<int:reservation_id>/park", methods=["PUT"])
@user_required
def mark_spot_occupied(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    current_user_username = get_jwt_identity() # This is now a string (username)
    user = User.query.filter_by(username=current_user_username).first()

    if reservation.user_id != user.id:
        return jsonify({"message": "Unauthorized to modify this reservation"}), 403
    
    if reservation.parking_timestamp:
        return jsonify({"message": "Vehicle already marked as parked for this reservation"}), 400

    spot = ParkingSpot.query.get(reservation.spot_id)
    if not spot:
         return jsonify({"message": "Associated parking spot not found"}), 404
    if spot.status == "O":
        pass 

    try:
        spot.status = "O"
        reservation.parking_timestamp = datetime.datetime.utcnow()
        db.session.commit()
        return jsonify({"message": "Vehicle parked successfully. Spot status updated to Occupied.", "parking_timestamp": reservation.parking_timestamp.isoformat()}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking spot as occupied: {e}")
        return jsonify({"message": "Error marking spot as occupied", "error": str(e)}), 500

@user_routes_bp.route("/reservations/<int:reservation_id>/vacate", methods=["PUT"])
@user_required
def mark_spot_vacated(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    current_user_username = get_jwt_identity() # This is now a string (username)
    user = User.query.filter_by(username=current_user_username).first()

    if reservation.user_id != user.id:
        return jsonify({"message": "Unauthorized to modify this reservation"}), 403

    if not reservation.parking_timestamp:
        return jsonify({"message": "Vehicle was never marked as parked for this reservation"}), 400
    
    if reservation.leaving_timestamp:
        return jsonify({"message": "Vehicle already marked as vacated for this reservation"}), 400

    spot = ParkingSpot.query.get(reservation.spot_id)
    if not spot:
         return jsonify({"message": "Associated parking spot not found"}), 404

    try:
        spot.status = "A"
        reservation.leaving_timestamp = datetime.datetime.utcnow()
        
        parking_duration_seconds = (reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds()
        parking_duration_hours = parking_duration_seconds / 3600
        
        lot = ParkingLot.query.get(spot.lot_id)
        price_per_hour = lot.price if lot else 0
        
        reservation.parking_cost = parking_duration_hours * price_per_hour
        reservation.parking_cost = round(max(0, reservation.parking_cost), 2) 

        db.session.commit()
        return jsonify({
            "message": "Vehicle vacated successfully. Spot status updated to Available.", 
            "leaving_timestamp": reservation.leaving_timestamp.isoformat(),
            "parking_duration_hours": round(parking_duration_hours, 2),
            "parking_cost": reservation.parking_cost
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking spot as vacated: {e}")
        return jsonify({"message": "Error marking spot as vacated", "error": str(e)}), 500

@user_routes_bp.route("/dashboard/summary", methods=["GET"])
@user_required
def user_dashboard_summary():
    current_user_username = get_jwt_identity() # This is now a string (username)
    user = User.query.filter_by(username=current_user_username).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    reservations = Reservation.query.filter_by(user_id=user.id).all()
    total_bookings = len(reservations)
    total_spent = sum(r.parking_cost for r in reservations if r.parking_cost is not None)
    
    active_reservation = Reservation.query.filter(Reservation.user_id == user.id, Reservation.leaving_timestamp.is_(None), Reservation.parking_timestamp.isnot(None)).first()
    active_reservation_details = None
    if active_reservation:
        spot = ParkingSpot.query.get(active_reservation.spot_id)
        lot = ParkingLot.query.get(spot.lot_id) if spot else None
        active_reservation_details = {
            "reservation_id": active_reservation.id,
            "spot_id": active_reservation.spot_id,
            "spot_number": spot.spot_number if spot else "N/A",
            "lot_name": lot.prime_location_name if lot else "N/A",
            "parking_timestamp": active_reservation.parking_timestamp.isoformat()
        }

    return jsonify({
        "total_bookings": total_bookings,
        "total_amount_spent": round(total_spent, 2),
        "active_reservation": active_reservation_details
    }), 200

@user_routes_bp.route("/export_reservations_csv", methods=["GET"])
@user_required
def export_reservations_csv():
    current_user_username = get_jwt_identity() # This is now a string (username)
    user = User.query.filter_by(username=current_user_username).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    reservations = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.parking_timestamp.desc()).all()

    if not reservations:
        return jsonify({"message": "No reservation history found for this user."}), 404

    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Reservation ID", "Lot Name", "Spot Number", "Parking Timestamp", "Leaving Timestamp", "Duration (Hours)", "Cost", "Address", "PIN Code"])
    
    for res in reservations:
        spot = ParkingSpot.query.get(res.spot_id)
        lot = ParkingLot.query.get(spot.lot_id) if spot else None
        duration_hours = "N/A"
        if res.parking_timestamp and res.leaving_timestamp:
            duration_seconds = (res.leaving_timestamp - res.parking_timestamp).total_seconds()
            duration_hours = round(duration_seconds / 3600, 2)

        writer.writerow([
            res.id,
            lot.prime_location_name if lot else "N/A",
            spot.spot_number if spot else "N/A",
            res.parking_timestamp.isoformat() if res.parking_timestamp else "N/A",
            res.leaving_timestamp.isoformat() if res.leaving_timestamp else "N/A",
            duration_hours,
            res.parking_cost if res.parking_cost is not None else "N/A",
            lot.address if lot else "N/A",
            lot.pin_code if lot else "N/A"
        ])
    
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{user.username}_parking_history.csv"
    )

