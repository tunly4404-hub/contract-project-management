import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, storage

def initialize_firebase():
    """
    Initializes Firebase Admin SDK and returns a tuple of (firestore_client, storage_bucket).
    First tries to read credentials from the Environment Variable 'FIREBASE_CREDENTIALS'
    (either as a JSON string or a file path).
    Falls back to 'serviceAccountKey.json' in the current working directory.
    """
    db_client = None
    bucket_client = None
    project_id = None

    try:
        # Check if firebase is already initialized
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
                    project_id = cred_dict.get("project_id")
                    print("Firebase credentials parsed from FIREBASE_CREDENTIALS env (JSON string).")
                except json.JSONDecodeError:
                    # 2. If it's not valid JSON, treat it as a path to a credentials JSON file
                    if os.path.exists(cred_env):
                        cred = credentials.Certificate(cred_env)
                        try:
                            with open(cred_env, "r") as f:
                                project_id = json.load(f).get("project_id")
                        except Exception:
                            pass
                        print(f"Firebase credentials loaded from file path in FIREBASE_CREDENTIALS: {cred_env}")
                    else:
                        print(f"Warning: FIREBASE_CREDENTIALS is set but is not valid JSON and does not point to an existing file: {cred_env}")

            # 3. Fallback to local serviceAccountKey.json file
            if not cred:
                local_key = "serviceAccountKey.json"
                if os.path.exists(local_key):
                    cred = credentials.Certificate(local_key)
                    try:
                        with open(local_key, "r") as f:
                            project_id = json.load(f).get("project_id")
                    except Exception:
                        pass
                    print(f"Firebase credentials loaded from local file: {local_key}")
                else:
                    # 4. Fallback to Application Default Credentials
                    try:
                        cred = credentials.ApplicationDefault()
                        print("Firebase initialized using Application Default Credentials.")
                    except Exception as e:
                        print(f"Warning: Application Default Credentials not available: {e}")

            # Setup default storage bucket
            # In Firebase, the default bucket name is typically '<PROJECT_ID>.firebasestorage.app' for newer projects
            storage_bucket_name = f"{project_id}.firebasestorage.app" if project_id else None
            
            # Initialize the app
            if cred:
                if storage_bucket_name:
                    firebase_admin.initialize_app(cred, {"storageBucket": storage_bucket_name})
                    print(f"Firebase Admin initialized with default storageBucket: {storage_bucket_name}")
                else:
                    firebase_admin.initialize_app(cred)
            else:
                print("No credentials found. Initializing Firebase Admin with default configuration (Metadata server / GCP environment).")
                firebase_admin.initialize_app()

        # Get clients
        db_client = firestore.client()
        try:
            bucket_client = storage.bucket()
            print("Firebase Storage bucket client initialized successfully.")
        except Exception as storage_err:
            print(f"Warning: Failed to initialize Firebase Storage bucket client: {storage_err}")
            bucket_client = None

    except Exception as e:
        print(f"Error during Firebase initialization: {e}")

    return db_client, bucket_client

# Create shared database and storage clients
try:
    db, bucket = initialize_firebase()
except Exception as e:
    print(f"Failed to initialize Firebase database and storage: {e}")
    db, bucket = None, None
