from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore, auth
from functools import wraps
import uuid
from flask_cors import CORS
import requests
from functools import wraps
app = Flask(__name__)
CORS(app)
# Initialize Firebase
cred = credentials.Certificate(
    "unite-5259c-firebase-adminsdk-fbsvc-a242c60250.json")
firebase_admin.initialize_app(cred)
db = firestore.client()


@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    required_fields = ['first_name', 'last_name', 'email', 'password']
    print(data)
    
    # Validate input
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing fields"}), 400

    try:
        # Create user in Firebase Auth
        user = auth.create_user(
            email=data['email'],
            password=data['password'],
            display_name=f"{data['first_name']} {data['last_name']}")

        # Save extra profile info in Firestore
        db.collection('users').document(user.uid).set({
            "first_name":
            data['first_name'],
            "last_name":
            data['last_name'],
            "email":
            data['email'],
            "uid":
            user.uid,
            "friends": [],
            "sessions": {}
        })

        return jsonify({"message": "User created", "uid": user.uid}), 201

    except auth.EmailAlreadyExistsError:
        return jsonify({"error": "Email already in use"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    #return jsonify({"message": "User created"}), 201


FIREBASE_API_KEY = "{api_key}"

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    # Firebase REST API endpoint
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        auth_data = res.json()
        return jsonify({
            "idToken": auth_data["idToken"],
            "refreshToken": auth_data["refreshToken"],
            "uid": auth_data["localId"]
        }), 200
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Login failed", "details": str(e)}), 401

def verify_firebase_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401

        id_token = auth_header.split("Bearer ")[1]

        try:
            decoded_token = auth.verify_id_token(id_token)
            request.uid = decoded_token['uid']  # Attach UID to request
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": "Invalid or expired token", "details": str(e)}), 401

    return decorated_function

@app.route('/profile', methods=['GET'])
@verify_firebase_token
def get_profile():
    uid = request.uid
    user_doc = db.collection('users').document(uid).get()

    if not user_doc.exists:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user_doc.to_dict()), 200

@app.route('/profile', methods=['POST'])
@verify_firebase_token
def update_profile():
    uid = request.uid
    data = request.get_json()

    if not data:
        return jsonify({"error": "Missing profile data"}), 400

    try:
        user_ref = db.collection('users').document(uid)

        # Merge with existing data (Firestore-style update)
        user_ref.set({
            "profile": data
        }, merge=True)

        return jsonify({"message": "Profile updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Profile update failed", "details": str(e)}), 500

@app.route('/session', methods=['POST'])
@verify_firebase_token
def create_session():
    uid = request.uid
    data = request.get_json()

    required_fields = [
        "title", "goal", "session_date",
        "session_start", "session_end",
        "location", "extra_location_details"
    ]

    # Check for missing fields
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    try:
        session_data = {
            "host": uid,
            "title": data["title"],
            "goal": data["goal"],
            "session_date": data["session_date"],
            "session_start": data["session_start"],
            "session_end": data["session_end"],
            "location": data["location"],
            "extra_location_details":data["extra_location_details"]
        }

        # Add to Firestore (auto-generated ID)
        session_ref = db.collection("sessions").add(session_data)

        return jsonify({
            "message": "Session created successfully",
            "session_id": session_ref[1].id
        }), 201

    except Exception as e:
        return jsonify({"error": "Failed to create session", "details": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0')