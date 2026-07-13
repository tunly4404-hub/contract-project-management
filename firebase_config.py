import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

def initialize_firebase():
    """
    Initializes Firebase Admin SDK and returns a Firestore client.
    First tries to read credentials from the Environment Variable 'FIREBASE_CREDENTIALS'
    (either as a JSON string or a file path).
    Falls back to 'serviceAccountKey.json' in the current working directory.
    Falls back to Application Default Credentials if neither is available.
    """
    # Check if firebase is already initialized to avoid duplicate initialization errors
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = None
        cred_env = os.environ.get("FIREBASE_CREDENTIALS")

        if cred_env:
            # 1. Try parsing env as JSON string
            try:
                cred_dict = json.loads(cred_env)
                cred = credentials.Certificate(cred_dict)
                print("Firebase initialized using credentials from FIREBASE_CREDENTIALS env (JSON string).")
            except json.JSONDecodeError:
                # 2. If it's not valid JSON, treat it as a path to a credentials JSON file
                if os.path.exists(cred_env):
                    cred = credentials.Certificate(cred_env)
                    print(f"Firebase initialized using credentials from file path in FIREBASE_CREDENTIALS: {cred_env}")
                else:
                    print(f"Warning: FIREBASE_CREDENTIALS is set but is not valid JSON and does not point to an existing file: {cred_env}")

        # 3. Fallback to local serviceAccountKey.json file
        if not cred:
            local_key = "serviceAccountKey.json"
            if os.path.exists(local_key):
                cred = credentials.Certificate(local_key)
                print(f"Firebase initialized using local file: {local_key}")
            else:
                # 4. Fallback to Application Default Credentials (e.g. running in Google Cloud environment)
                try:
                    cred = credentials.ApplicationDefault()
                    print("Firebase initialized using Application Default Credentials.")
                except Exception as e:
                    print(f"Warning: Application Default Credentials not available: {e}")

        # Initialize the app
        if cred:
            firebase_admin.initialize_app(cred)
        else:
            print("No credentials found. Initializing Firebase Admin with default configuration (Metadata server / GCP environment).")
            firebase_admin.initialize_app()

    try:
        return firestore.client()
    except Exception as e:
        print(f"Error initializing Firestore client: {e}")
        return None

# Create a shared firestore client instance
try:
    db = initialize_firebase()
except Exception as e:
    print(f"Failed to initialize Firebase database: {e}")
    db = None

