import os
import json
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------
# Firebase Admin SDK Configuration
# ---------------------------------------------------------
firebase_initialized = False
firestore_client = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    firebase_creds_raw = os.getenv("FIREBASE_CREDENTIALS")
    if firebase_creds_raw:
        try:
            creds_dict = json.loads(firebase_creds_raw)
            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred)
            firestore_client = firestore.client()
            firebase_initialized = True
            print("Successfully connected to Firebase Firestore from environment variable.")
        except Exception as e:
            print(f"Warning: Failed to connect to Firebase using environment variable. Error: {e}")
            
    elif os.path.exists("firebase_credentials.json"):
        try:
            cred = credentials.Certificate("firebase_credentials.json")
            firebase_admin.initialize_app(cred)
            firestore_client = firestore.client()
            firebase_initialized = True
            print("Successfully connected to Firebase Firestore from local firebase_credentials.json.")
        except Exception as e:
            print(f"Warning: Failed to connect to Firebase using local JSON. Error: {e}")
except Exception as e:
    print(f"Warning: Firebase libraries not available or failed to load. Error: {e}")


# ---------------------------------------------------------
# SQLAlchemy Fallback Configuration
# ---------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or not DATABASE_URL.strip():
    persistent_dir = "/data" if os.path.exists("/data") and os.path.isdir("/data") else "."
    DATABASE_URL = f"sqlite:///{persistent_dir}/projects.db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    try:
        temp_engine = create_engine(DATABASE_URL)
        with temp_engine.connect() as conn:
            pass
        engine = create_engine(
            DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800
        )
        print("Successfully connected to external PostgreSQL database.")
    except Exception as e:
        print(f"Warning: Failed to connect to PostgreSQL database. Falling back to local SQLite. Error: {e}")
        persistent_dir = "/data" if os.path.exists("/data") and os.path.isdir("/data") else "."
        DATABASE_URL = f"sqlite:///{persistent_dir}/projects.db"
        engine = create_engine(
            DATABASE_URL, connect_args={"check_same_thread": False}
        )

_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def SessionLocal():
    if firebase_initialized and firestore_client is not None:
        return FirestoreSession(firestore_client)
    return _SessionLocal()

Base = declarative_base()


# ---------------------------------------------------------
# Firestore Adapter Classes (SQLAlchemy Mock)
# ---------------------------------------------------------
class FirestoreModel:
    def __init__(self, doc_id, data, collection_name=None, db=None):
        self._doc_id = doc_id
        self._data = data or {}
        self._collection_name = collection_name
        self._db = db
        
        # Populate client-facing 'id' attribute as an integer if possible (or keep as is)
        if "id" in self._data:
            try:
                self.id = int(self._data["id"])
            except ValueError:
                self.id = self._data["id"]
        elif doc_id and doc_id.isdigit():
            self.id = int(doc_id)
        else:
            self.id = doc_id
        
    def __getattr__(self, name):
        if name in self._data:
            val = self._data[name]
            if isinstance(val, str):
                # Auto-parse dates and datetimes
                if name in ["due_date", "start_date", "end_date", "contract_signing_date", "counterpart_date", "guarantee_receipt_date", "guarantee_expiry_date", "work_order_date", "po_date", "delivery_date"]:
                    try:
                        return date.fromisoformat(val[:10])
                    except Exception:
                        pass
                elif name in ["created_at", "updated_at", "timestamp"]:
                    try:
                        return datetime.fromisoformat(val)
                    except Exception:
                        pass
            return val
            
        # Resolve relationships (lazy-loaded queries)
        if name == "deliverables":
            if not self._db: return []
            docs = self._db.collection("deliverables").where("project_id", "==", self.id).stream()
            return [FirestoreModel(d.id, d.to_dict(), "deliverables", self._db) for d in docs]
        if name == "purchase_orders":
            if not self._db: return []
            docs = self._db.collection("purchase_orders").where("project_id", "==", self.id).stream()
            return [FirestoreModel(d.id, d.to_dict(), "purchase_orders", self._db) for d in docs]
        if name == "documents":
            if not self._db: return []
            docs = self._db.collection("documents").where("project_id", "==", self.id).stream()
            return [FirestoreModel(d.id, d.to_dict(), "documents", self._db) for d in docs]
        if name == "project":
            if not self._db or "project_id" not in self._data: return None
            project_id = self._data["project_id"]
            if not project_id: return None
            doc = self._db.collection("projects").document(str(project_id)).get()
            if doc.exists:
                return FirestoreModel(doc.id, doc.to_dict(), "projects", self._db)
            return None
            
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        if name in ["id", "_doc_id", "_data", "_collection_name", "_db"]:
            super().__setattr__(name, value)
        else:
            db_value = value
            if isinstance(value, (date, datetime)):
                db_value = value.isoformat()
                
            self._data[name] = db_value
            # Persist update immediately to Firestore
            if self._db and self._collection_name and self._doc_id:
                doc_ref = self._db.collection(self._collection_name).document(str(self._doc_id))
                doc_ref.update({name: db_value})


class FirestoreQuery:
    def __init__(self, client, model_class, filters=None, orders=None):
        self.client = client
        self.model_class = model_class
        self.collection_name = self._get_collection_name(model_class)
        self.filters = filters or []
        self.orders = orders or []
        
    def _get_collection_name(self, model_class):
        import models
        name_map = {
            models.User: "users",
            models.Project: "projects",
            models.Deliverable: "deliverables",
            models.Document: "documents",
            models.PurchaseOrder: "purchase_orders",
            models.AuditLog: "audit_logs"
        }
        return name_map.get(model_class, model_class.__name__.lower() + "s")
        
    def filter(self, *criterion):
        new_filters = list(self.filters)
        for cond in criterion:
            try:
                # SQLAlchemy BinaryExpression extraction: (field == value)
                field = cond.left.name
                val = cond.right.value
                new_filters.append((field, "==", val))
            except Exception:
                pass
        return FirestoreQuery(self.client, self.model_class, new_filters, self.orders)
        
    def order_by(self, *criterion):
        new_orders = list(self.orders)
        for order in criterion:
            try:
                field = order.element.name
                direction = "desc" if "desc" in str(order.modifier).lower() else "asc"
                new_orders.append((field, direction))
            except Exception:
                try:
                    field = order.name
                    new_orders.append((field, "asc"))
                except Exception:
                    pass
        return FirestoreQuery(self.client, self.model_class, self.filters, new_orders)
        
    def first(self):
        ref = self.client.collection(self.collection_name)
        for field, op, val in self.filters:
            ref = ref.where(field, op, val)
        docs = list(ref.limit(1).stream())
        if docs:
            return FirestoreModel(docs[0].id, docs[0].to_dict(), self.collection_name, self.client)
        return None
        
    def all(self):
        ref = self.client.collection(self.collection_name)
        for field, op, val in self.filters:
            ref = ref.where(field, op, val)
        for field, direction in self.orders:
            ref = ref.order_by(field, direction="DESCENDING" if direction == "desc" else "ASCENDING")
        docs = ref.stream()
        return [FirestoreModel(d.id, d.to_dict(), self.collection_name, self.client) for d in docs]
        
    def offset(self, skip):
        return self
        
    def limit(self, limit):
        return self

    def delete(self):
        docs = self.all()
        for doc in docs:
            self.client.collection(self.collection_name).document(str(doc._doc_id)).delete()


class FirestoreSession:
    def __init__(self, client):
        self.client = client
        self._added_objects = []
        
    def query(self, model_class):
        return FirestoreQuery(self.client, model_class)
        
    def commit(self):
        # Persist post-add attribute updates on tracked SQLAlchemy models
        for obj in self._added_objects:
            collection_name = getattr(obj, "_collection_name", None)
            doc_id = getattr(obj, "_doc_id", None)
            if collection_name and doc_id:
                data = {}
                for column in obj.__table__.columns:
                    val = getattr(obj, column.name)
                    if isinstance(val, (date, datetime)):
                        val = val.isoformat()
                    data[column.name] = val
                self.client.collection(collection_name).document(str(doc_id)).set(data)

    def rollback(self):
        self._added_objects = []

    def flush(self):
        pass

    def add_all(self, objects):
        for obj in objects:
            self.add(obj)
        
    def refresh(self, obj):
        doc_id = getattr(obj, "_doc_id", None)
        collection_name = getattr(obj, "_collection_name", None)
        if obj and collection_name and doc_id:
            doc = self.client.collection(collection_name).document(str(doc_id)).get()
            if doc.exists:
                obj._data = doc.to_dict()
                if "id" not in obj._data:
                    obj._data["id"] = doc.id
                    
    def add(self, obj):
        if obj is None:
            return
            
        if obj not in self._added_objects:
            self._added_objects.append(obj)
            
        import models
        model_class = obj.__class__
        name_map = {
            models.User: "users",
            models.Project: "projects",
            models.Deliverable: "deliverables",
            models.Document: "documents",
            models.PurchaseOrder: "purchase_orders",
            models.AuditLog: "audit_logs"
        }
        collection_name = name_map.get(model_class, model_class.__name__.lower() + "s")
        
        # Serialize fields from SQLAlchemy model to a dict
        data = {}
        for column in obj.__table__.columns:
            val = getattr(obj, column.name)
            if isinstance(val, (date, datetime)):
                val = val.isoformat()
            data[column.name] = val
            
        if "id" in data and (data["id"] is None or isinstance(data["id"], int)):
            data.pop("id", None)
            
        # Atomic sequence ID generation using a counter document
        @firestore.transactional
        def get_next_id(transaction, counter_ref):
            snapshot = counter_ref.get(transaction=transaction)
            if snapshot.exists:
                last_id = snapshot.get("last_id")
                next_id = last_id + 1
                transaction.update(counter_ref, {"last_id": next_id})
            else:
                next_id = 1
                transaction.set(counter_ref, {"last_id": next_id})
            return next_id
            
        counter_ref = self.client.collection("counters").document(collection_name)
        transaction = self.client.transaction()
        next_id = get_next_id(transaction, counter_ref)
        
        data["id"] = next_id
        obj.id = next_id
        
        # Write to Firestore
        if collection_name == "users" and "username" in data and data["username"]:
            # Keep document ID as username for fast lookups, but store integer 'id'
            doc_ref = self.client.collection(collection_name).document(data["username"])
            doc_ref.set(data)
            obj._doc_id = data["username"]
        else:
            # Document ID is the string representation of the integer ID
            doc_ref = self.client.collection(collection_name).document(str(next_id))
            doc_ref.set(data)
            obj._doc_id = str(next_id)
            
        obj._collection_name = collection_name
        
    def delete(self, obj):
        collection_name = None
        doc_id = None
        
        if isinstance(obj, FirestoreModel):
            collection_name = obj._collection_name
            doc_id = obj._doc_id
        else:
            import models
            model_class = obj.__class__
            name_map = {
                models.User: "users",
                models.Project: "projects",
                models.Deliverable: "deliverables",
                models.Document: "documents",
                models.PurchaseOrder: "purchase_orders",
                models.AuditLog: "audit_logs"
            }
            collection_name = name_map.get(model_class)
            # If it's user, document ID is username
            if collection_name == "users":
                doc_id = getattr(obj, "username", None)
            else:
                doc_id = getattr(obj, "id", None)
                
        if collection_name and doc_id:
            self.client.collection(collection_name).document(str(doc_id)).delete()
            
    def close(self):
        pass


# ---------------------------------------------------------
# DB Dependency Yield logic
# ---------------------------------------------------------
def get_db():
    if firebase_initialized and firestore_client is not None:
        db = FirestoreSession(firestore_client)
        try:
            yield db
        finally:
            db.close()
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
