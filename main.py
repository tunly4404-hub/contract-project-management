import os
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
import shutil
import jwt
import urllib.parse
import requests

import schemas
import crud
import excel_export
from firebase_config import db as firestore_db, bucket as firebase_bucket

app = FastAPI(title="Smart Contract & Purchase Order Management System")

# Secret key and algorithm for JWT security
SECRET_KEY = "ANTIGRAVITY_V5_SECRET_KEY_JWT_SECURITY_HASH"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 180

# Auto-seed database users (admin and user account) on startup
def auto_seed_db():
    if firestore_db is None:
        print("Skipping database auto-seeding: Firestore connection is not initialized.")
        return
    try:
        admin_doc_ref = firestore_db.collection("users").document("admin")
        if not admin_doc_ref.get().exists:
            print("Auto-seeding default admin account on startup...")
            admin_schema = schemas.UserCreate(
                username="admin",
                fullname="ผู้ดูแลระบบหลัก",
                role="admin",
                password="admin1234"
            )
            crud.create_user(firestore_db, admin_schema)
            admin_doc_ref.update({"role": "admin", "is_active": True})
            
        sittipan_doc_ref = firestore_db.collection("users").document("sittipan")
        if not sittipan_doc_ref.get().exists:
            print("Auto-seeding default sittipan account on startup...")
            sittipan_schema = schemas.UserCreate(
                username="sittipan",
                fullname="คุณ สิทธิพรรณ",
                role="user",
                password="sittipan123"
            )
            crud.create_user(firestore_db, sittipan_schema)
            sittipan_doc_ref.update({"role": "user", "is_active": True})
    except Exception as e:
        print(f"Error during database auto-seeding: {e}")

auto_seed_db()

# Support persistent directory (e.g. Render Disk mounted at /data)
PERSISTENT_DIR = "/data" if os.path.exists("/data") and os.path.isdir("/data") else "."
UPLOAD_DIR = os.path.join(PERSISTENT_DIR, "uploads")
UPLOAD_PO_DIR = os.path.join(UPLOAD_DIR, "pos")
UPLOAD_DELIVERY_DIR = os.path.join(UPLOAD_DIR, "deliveries")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(UPLOAD_PO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DELIVERY_DIR, exist_ok=True)

# Firebase Cloud Storage upload/delete helper functions
def upload_to_firebase_storage(file_content: bytes, filename: str, subfolder: str, content_type: str) -> Optional[str]:
    """
    Uploads file content to Firebase Cloud Storage if configured.
    Returns the public URL if successful, or None if Firebase Storage is not initialized.
    """
    if firebase_bucket is None:
        print("Firebase Storage is not initialized. Falling back to local storage.")
        return None
        
    try:
        # Determine unique file path in bucket
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        blob_path = f"{subfolder}/{timestamp}_{filename}"
        blob = firebase_bucket.blob(blob_path)
        
        # Upload content
        blob.upload_from_string(file_content, content_type=content_type)
        
        # Make the file public so others can download/view it
        blob.make_public()
        
        # Return the public URL
        return blob.public_url
    except Exception as e:
        print(f"Firebase Storage upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file to Firebase Storage: {str(e)}")

def delete_from_firebase_storage(public_url: str):
    """
    Deletes the file from Firebase Storage.
    """
    if firebase_bucket is None or not public_url:
        return
        
    if "storage.googleapis.com" not in public_url:
        return
        
    try:
        bucket_name = firebase_bucket.name
        path_part = f"storage.googleapis.com/{bucket_name}/"
        if path_part in public_url:
            # Extract and unquote the path
            blob_path = urllib.parse.unquote(public_url.split(path_part)[1])
            blob = firebase_bucket.blob(blob_path)
            if blob.exists():
                blob.delete()
                print(f"Deleted file {blob_path} from Firebase Storage.")
    except Exception as e:
        print(f"Failed to delete file from Firebase Storage: {e}")

def get_db():
    return firestore_db

# Helper function to generate JWT access tokens
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except jwt.PyJWTError:
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user_username(token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_dict = crud.get_user_by_username(db, username=username)
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    user = excel_export.DictObject(user_dict)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="บัญชีผู้ใช้งานนี้ยังไม่ได้รับการอนุมัติจากผู้ดูแลระบบ (Admin) หรือถูกระงับสิทธิ์เข้าใช้งาน กรุณาติดต่อผู้ดูแลระบบเพื่ออนุมัติสิทธิ์เข้าใช้งาน",
        )
    return user.username

def check_admin_role(token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    username = get_current_user_username(token, db)
    user_dict = crud.get_user_by_username(db, username=username)
    user = excel_export.DictObject(user_dict)
    if not user or user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="สิทธิ์การใช้งานไม่เพียงพอ: จำเป็นต้องใช้สิทธิ์ผู้ดูแลระบบ (Admin) เท่านั้น"
        )
    return user

# Helper validation function for uploads
def validate_uploaded_file(file: UploadFile):
    _, ext = os.path.splitext(file.filename)
    ext = ext.lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Only PDF, PNG, JPG, and JPEG are allowed.")
    try:
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read file size")
    if file_size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds the 50MB limit")

# Helper function to populate relations of project dictionaries
def populate_project_relations(db, p):
    if not p:
        return None
    project_id = p["id"]
    
    # 1. Fetch deliverables
    delivs = db.collection("deliverables").where("project_id", "==", project_id).stream()
    p["deliverables"] = []
    for d in delivs:
        d_data = d.to_dict()
        d_data["id"] = d.id
        p["deliverables"].append(d_data)
        
    # 2. Fetch purchase orders
    pos = db.collection("purchase_orders").where("project_id", "==", project_id).stream()
    p["purchase_orders"] = []
    for po in pos:
        po_data = po.to_dict()
        po_data["id"] = po.id
        p["purchase_orders"].append(po_data)
        
    # 3. Fetch documents
    docs = db.collection("documents").where("project_id", "==", project_id).stream()
    p["documents"] = []
    for doc in docs:
        doc_data = doc.to_dict()
        doc_data["id"] = doc.id
        p["documents"].append(doc_data)
        
    return p

# Helper function to populate PO project information
def populate_po_project(db, po):
    if not po:
        return None
    project_id = po.get("project_id")
    if project_id:
        po["project"] = crud.get_project(db, project_id)
    else:
        po["project"] = None
    return po


# Authentication Routes
@app.post("/api/auth/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.post("/api/auth/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db = Depends(get_db)):
    user_dict = crud.get_user_by_username(db, username=user_credentials.username)
    if not user_dict or not crud.verify_password(user_credentials.password, user_dict.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    user = excel_export.DictObject(user_dict)
    if not user.is_active:
        raise HTTPException(
            status_code=400, 
            detail="บัญชีผู้ใช้งานนี้ยังไม่ได้รับการอนุมัติจากผู้ดูแลระบบ (Admin) หรือถูกระงับสิทธิ์เข้าใช้งาน"
        )
        
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_dict
    }

@app.get("/api/auth/me", response_model=schemas.UserResponse)
def get_me(username: str = Depends(get_current_user_username), db = Depends(get_db)):
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# User Management Endpoints (Admin Only)
@app.get("/api/users", response_model=List[schemas.UserResponse])
def get_all_users(current_admin = Depends(check_admin_role), db = Depends(get_db)):
    if db is None:
        return []
    docs = db.collection("users").stream()
    users = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        users.append(data)
    return users

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str, current_admin = Depends(check_admin_role), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    admin = excel_export.DictObject(current_admin)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="ไม่สามารถลบบัญชีผู้ใช้งานของตนเองได้")
    
    doc_ref = db.collection("users").document(user_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้ในระบบ")
        
    doc_ref.delete()
    return {"detail": "User deleted successfully"}

@app.put("/api/users/{user_id}/toggle-active", response_model=schemas.UserResponse)
def toggle_user_active(user_id: str, current_admin = Depends(check_admin_role), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    admin = excel_export.DictObject(current_admin)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="ไม่สามารถระงับสิทธิ์บัญชีผู้ใช้งานของตนเองได้")
        
    doc_ref = db.collection("users").document(user_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้ในระบบ")
        
    user_data = doc.to_dict()
    new_active = not user_data.get("is_active", True)
    doc_ref.update({"is_active": new_active})
    
    user_data["is_active"] = new_active
    user_data["id"] = doc.id
    return user_data

@app.put("/api/users/{user_id}/reset-password")
def reset_user_password(user_id: str, payload: schemas.UserResetPassword, current_admin = Depends(check_admin_role), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    doc_ref = db.collection("users").document(user_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้ในระบบ")
        
    hashed_pwd = crud.get_password_hash(payload.new_password)
    doc_ref.update({"hashed_password": hashed_pwd})
    return {"detail": f"เปลี่ยนรหัสผ่านสำหรับผู้ใช้งาน {user_id} เรียบร้อยแล้ว"}

@app.get("/api/admin/disk-usage")
def get_disk_usage(current_admin = Depends(check_admin_role)):
    try:
        if firebase_bucket is None:
            total, used, free = shutil.disk_usage(PERSISTENT_DIR)
            return {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "percentage_used": round((used / total) * 100, 2)
            }
        
        # Calculate used space by listing blobs in Firebase Storage
        blobs = firebase_bucket.list_blobs()
        used = sum(blob.size for blob in blobs if blob.size is not None)
        
        # Free tier is 5 GB
        total = 5 * 1024 * 1024 * 1024
        free = max(0, total - used)
        percentage = round((used / total) * 100, 2) if total > 0 else 0.0
        
        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "percentage_used": percentage
        }
    except Exception as e:
        # Fallback to local disk usage on error
        try:
            total, used, free = shutil.disk_usage(PERSISTENT_DIR)
            return {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "percentage_used": round((used / total) * 100, 2)
            }
        except Exception:
            raise HTTPException(status_code=500, detail=f"Failed to read storage usage: {str(e)}")

@app.get("/api/audit-logs", response_model=List[schemas.AuditLogResponse])
def get_audit_logs(
    username: str = Depends(get_current_user_username),
    db = Depends(get_db)
):
    if db is None:
        return []
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    logs_ref = db.collection("audit_logs")
    if user.get("role") == "admin":
        docs = logs_ref.stream()
    else:
        docs = logs_ref.where("username", "==", username).stream()
        
    logs = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        logs.append(data)
        
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return logs


# Dashboard Endpoints
@app.get("/api/dashboard/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(username: str = Depends(get_current_user_username), db = Depends(get_db)):
    return crud.get_dashboard_stats(db)

@app.get("/api/dashboard/alerts", response_model=List[schemas.DashboardAlert])
def get_dashboard_alerts(username: str = Depends(get_current_user_username), db = Depends(get_db)):
    return crud.get_dashboard_alerts(db)

@app.get("/api/dashboard/po-alerts", response_model=List[schemas.DashboardPOAlert])
def get_dashboard_po_alerts(username: str = Depends(get_current_user_username), db = Depends(get_db)):
    return crud.get_dashboard_po_alerts(db)


# Project Endpoints
@app.get("/api/projects", response_model=List[schemas.Project])
def read_projects(skip: int = 0, limit: int = 100, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    projects = crud.get_projects(db, skip=skip, limit=limit)
    return [populate_project_relations(db, p) for p in projects]

@app.get("/api/projects/{project_id}", response_model=schemas.Project)
def read_project(project_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return populate_project_relations(db, db_project)

@app.post("/api/projects", response_model=schemas.Project)
def create_project(project: schemas.ProjectCreate, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_project = crud.create_project(db=db, project=project, username=username)
    crud.log_user_action(db, username, "สร้าง", "โครงการ", db_project.get("name"), f"งบประมาณ: {db_project.get('budget')} บาท")
    return populate_project_relations(db, db_project)

@app.put("/api/projects/{project_id}", response_model=schemas.Project)
def update_project(project_id: str, project: schemas.ProjectUpdate, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_project_old = crud.get_project(db, project_id)
    if not db_project_old:
        raise HTTPException(status_code=404, detail="Project not found")
    db_project = crud.update_project(db=db, project_id=project_id, project=project, username=username)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    crud.log_user_action(db, username, "แก้ไข", "โครงการ", db_project.get("name"), "แก้ไขข้อมูลโครงการ")
    return populate_project_relations(db, db_project)

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, current_admin = Depends(check_admin_role), db = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Delete uploaded documents in Firebase Storage before deleting project record
    docs = db.collection("documents").where("project_id", "==", project_id).stream()
    for doc in docs:
        d = doc.to_dict()
        if d.get("url_path"):
            delete_from_firebase_storage(d.get("url_path"))
            
    # Delete guarantee receipt and guarantee document from Firebase Storage
    if db_project.get("guarantee_receipt_path"):
        delete_from_firebase_storage(db_project.get("guarantee_receipt_path"))
    if db_project.get("guarantee_document_path"):
        delete_from_firebase_storage(db_project.get("guarantee_document_path"))

    # Also delete PO files from Firebase Storage associated with this project
    pos = db.collection("purchase_orders").where("project_id", "==", project_id).stream()
    for po_doc in pos:
        po = po_doc.to_dict()
        for path_key in ["po_file_path", "quotation_file_path", "delivery_file_path"]:
            if po.get(path_key):
                delete_from_firebase_storage(po.get(path_key))

    crud.log_user_action(db, current_admin.username, "ลบ", "โครงการ", db_project.get("name"), f"ลบโครงการ ID: {project_id}")
    success = crud.delete_project(db=db, project_id=project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"detail": "Project deleted successfully"}


# Deliverables Endpoints
@app.post("/api/projects/{project_id}/deliverables", response_model=schemas.Deliverable)
def create_project_deliverable(project_id: str, deliverable: schemas.DeliverableCreate, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    db_deliverable = crud.create_deliverable(db=db, deliverable=deliverable, project_id=project_id, username=username)
    crud.log_user_action(db, username, "สร้าง", "งวดงานสัญญาหลัก", db_deliverable.get("name"), f"สร้างงวดงานในโครงการ '{db_project.get('name')}'")
    return db_deliverable

@app.put("/api/deliverables/{deliverable_id}", response_model=schemas.Deliverable)
def update_deliverable(deliverable_id: str, deliverable: schemas.DeliverableUpdate, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_del = crud.get_deliverable(db, deliverable_id)
    if not db_del:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    db_deliverable = crud.update_deliverable(db=db, deliverable_id=deliverable_id, deliverable=deliverable, username=username)
    crud.log_user_action(db, username, "แก้ไข", "งวดงานสัญญาหลัก", db_deliverable.get("name"), f"แก้ไขรายละเอียดงวดงาน (สถานะ: {db_deliverable.get('status')})")
    return db_deliverable

@app.delete("/api/deliverables/{deliverable_id}")
def delete_deliverable(deliverable_id: str, current_admin = Depends(check_admin_role), db = Depends(get_db)):
    db_del = crud.get_deliverable(db, deliverable_id)
    if not db_del:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    crud.log_user_action(db, current_admin.username, "ลบ", "งวดงานสัญญาหลัก", db_del.get("name"), f"ลบงวดงาน ID: {deliverable_id}")
    success = crud.delete_deliverable(db=db, deliverable_id=deliverable_id)
    if not success:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    return {"detail": "Deliverable deleted successfully"}


# Purchase Order (PO) Endpoints
@app.get("/api/purchase-orders", response_model=List[schemas.PurchaseOrder])
def read_purchase_orders(username: str = Depends(get_current_user_username), db = Depends(get_db)):
    return crud.get_purchase_orders(db)

@app.get("/api/purchase-orders/{po_id}", response_model=schemas.PurchaseOrder)
def read_purchase_order(po_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    return db_po

@app.post("/api/projects/{project_id}/purchase-orders", response_model=schemas.PurchaseOrder)
def create_purchase_order(project_id: str, po: schemas.PurchaseOrderCreate, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    db_po = crud.create_purchase_order(db=db, po=po, project_id=project_id, username=username)
    crud.log_user_action(db, username, "สร้าง", "ใบสั่งซื้อ PO", db_po.get("po_number"), f"สร้างใบสั่งซื้อ PO งบประมาณ: {db_po.get('budget')} บาท ในโครงการ '{db_project.get('name')}'")
    return db_po

@app.put("/api/purchase-orders/{po_id}", response_model=schemas.PurchaseOrder)
def update_purchase_order(po_id: str, po: schemas.PurchaseOrderUpdate, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_po_old = crud.get_purchase_order(db, po_id)
    if not db_po_old:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    old_delivery_status = db_po_old.get("delivery_status")
    
    db_po = crud.update_purchase_order(db=db, po_id=po_id, po=po, username=username)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    if old_delivery_status != db_po.get("delivery_status"):
        crud.log_user_action(db, username, "แก้ไข", "ใบส่งมอบของ", f"PO: {db_po.get('po_number')}", f"ปรับปรุงการส่งมอบเป็น '{db_po.get('delivery_status')}' (เลขที่ใบส่งของ: {db_po.get('delivery_no') or '-'})")
    else:
        crud.log_user_action(db, username, "แก้ไข", "ใบสั่งซื้อ PO", db_po.get("po_number"), "แก้ไขรายละเอียดใบสั่งซื้อ")
    return db_po

@app.delete("/api/purchase-orders/{po_id}")
def delete_purchase_order(po_id: str, current_admin = Depends(check_admin_role), db = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    # Delete PO files from Firebase Cloud Storage
    for path in [db_po.get("po_file_path"), db_po.get("quotation_file_path"), db_po.get("delivery_file_path")]:
        if path:
            delete_from_firebase_storage(path)
            # Try fallback local files delete
            filename = os.path.basename(path)
            for folder in [UPLOAD_PO_DIR, UPLOAD_DELIVERY_DIR, UPLOAD_DIR]:
                file_path = os.path.join(folder, filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        break
                    except Exception:
                        pass
                        
    crud.log_user_action(db, current_admin.username, "ลบ", "ใบสั่งซื้อ PO", db_po.get("po_number"), f"ลบใบสั่งซื้อ ID: {po_id}")
    success = crud.delete_purchase_order(db=db, po_id=po_id)
    if not success:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    return {"detail": "Purchase Order deleted successfully"}


# PO Document Files Upload
@app.post("/api/purchase-orders/{po_id}/po-file", response_model=schemas.PurchaseOrder)
def upload_po_file(po_id: str, file: UploadFile = File(...), username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    validate_uploaded_file(file)
    try:
        file_content = file.file.read()
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        
    # Upload to Firebase Storage
    cloud_url = upload_to_firebase_storage(file_content, file.filename, "pos", file.content_type)
    if cloud_url:
        po_file_path = cloud_url
    else:
        # Fallback local upload
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_filename = f"po_{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_PO_DIR, safe_filename)
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        po_file_path = f"/uploads/pos/{safe_filename}"
        
    update_data = {
        "po_file_path": po_file_path,
        "po_file_filename": file.filename,
        "updated_by": username,
        "updated_at": datetime.utcnow().isoformat()
    }
    db.collection("purchase_orders").document(po_id).update(update_data)
    
    db_po.update(update_data)
    crud.log_user_action(db, username, "สร้าง", "ไฟล์ใบสั่งซื้อ PO", file.filename, f"อัปโหลดไฟล์ใบสั่งซื้อสำหรับ PO: {db_po.get('po_number')}")
    return db_po

@app.delete("/api/purchase-orders/{po_id}/po-file", response_model=schemas.PurchaseOrder)
def delete_po_file(po_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    po_file_path = db_po.get("po_file_path")
    if po_file_path:
        # Delete from Firebase Storage
        delete_from_firebase_storage(po_file_path)
        
        # Local fallback delete
        filename = os.path.basename(po_file_path)
        file_path = os.path.join(UPLOAD_PO_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
                
        orig_filename = db_po.get("po_file_filename")
        update_data = {
            "po_file_path": None,
            "po_file_filename": None,
            "updated_by": username,
            "updated_at": datetime.utcnow().isoformat()
        }
        db.collection("purchase_orders").document(po_id).update(update_data)
        db_po.update(update_data)
        crud.log_user_action(db, username, "ลบ", "ไฟล์ใบสั่งซื้อ PO", orig_filename, f"ลบไฟล์ใบสั่งซื้อสำหรับ PO: {db_po.get('po_number')}")
    return db_po

@app.post("/api/purchase-orders/{po_id}/quotation-file", response_model=schemas.PurchaseOrder)
def upload_quotation_file(po_id: str, file: UploadFile = File(...), username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    validate_uploaded_file(file)
    try:
        file_content = file.file.read()
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        
    cloud_url = upload_to_firebase_storage(file_content, file.filename, "pos", file.content_type)
    if cloud_url:
        quotation_file_path = cloud_url
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_filename = f"quot_{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_PO_DIR, safe_filename)
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        quotation_file_path = f"/uploads/pos/{safe_filename}"
        
    update_data = {
        "quotation_file_path": quotation_file_path,
        "quotation_file_filename": file.filename,
        "updated_by": username,
        "updated_at": datetime.utcnow().isoformat()
    }
    db.collection("purchase_orders").document(po_id).update(update_data)
    
    db_po.update(update_data)
    crud.log_user_action(db, username, "สร้าง", "ไฟล์ใบเสนอราคา PO", file.filename, f"อัปโหลดไฟล์ใบเสนอราคาสำหรับ PO: {db_po.get('po_number')}")
    return db_po

@app.delete("/api/purchase-orders/{po_id}/quotation-file", response_model=schemas.PurchaseOrder)
def delete_quotation_file(po_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    quot_path = db_po.get("quotation_file_path")
    if quot_path:
        delete_from_firebase_storage(quot_path)
        
        filename = os.path.basename(quot_path)
        file_path = os.path.join(UPLOAD_PO_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
                
        orig_filename = db_po.get("quotation_file_filename")
        update_data = {
            "quotation_file_path": None,
            "quotation_file_filename": None,
            "updated_by": username,
            "updated_at": datetime.utcnow().isoformat()
        }
        db.collection("purchase_orders").document(po_id).update(update_data)
        db_po.update(update_data)
        crud.log_user_action(db, username, "ลบ", "ไฟล์ใบเสนอราคา PO", orig_filename, f"ลบไฟล์ใบเสนอราคาสำหรับ PO: {db_po.get('po_number')}")
    return db_po

@app.post("/api/purchase-orders/{po_id}/delivery-file", response_model=schemas.PurchaseOrder)
def upload_delivery_file(po_id: str, file: UploadFile = File(...), username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    validate_uploaded_file(file)
    try:
        file_content = file.file.read()
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        
    cloud_url = upload_to_firebase_storage(file_content, file.filename, "deliveries", file.content_type)
    if cloud_url:
        delivery_file_path = cloud_url
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_filename = f"delivery_{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_DELIVERY_DIR, safe_filename)
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        delivery_file_path = f"/uploads/deliveries/{safe_filename}"
        
    update_data = {
        "delivery_file_path": delivery_file_path,
        "delivery_file_filename": file.filename,
        "updated_by": username,
        "updated_at": datetime.utcnow().isoformat()
    }
    db.collection("purchase_orders").document(po_id).update(update_data)
    
    db_po.update(update_data)
    crud.log_user_action(db, username, "สร้าง", "ไฟล์ใบส่งของ PO", file.filename, f"อัปโหลดไฟล์ใบส่งของสำหรับ PO: {db_po.get('po_number')}")
    return db_po

@app.delete("/api/purchase-orders/{po_id}/delivery-file", response_model=schemas.PurchaseOrder)
def delete_delivery_file(po_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    deliv_path = db_po.get("delivery_file_path")
    if deliv_path:
        delete_from_firebase_storage(deliv_path)
        
        filename = os.path.basename(deliv_path)
        file_path = os.path.join(UPLOAD_DELIVERY_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
                
        orig_filename = db_po.get("delivery_file_filename")
        update_data = {
            "delivery_file_path": None,
            "delivery_file_filename": None,
            "updated_by": username,
            "updated_at": datetime.utcnow().isoformat()
        }
        db.collection("purchase_orders").document(po_id).update(update_data)
        db_po.update(update_data)
        crud.log_user_action(db, username, "ลบ", "ไฟล์ใบส่งของ PO", orig_filename, f"ลบไฟล์ใบส่งของสำหรับ PO: {db_po.get('po_number')}")
    return db_po


# Contract Documents Upload
@app.post("/api/projects/{project_id}/documents", response_model=schemas.Document)
def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user_username),
    db = Depends(get_db)
):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    try:
        file_content = file.file.read()
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        
    cloud_url = upload_to_firebase_storage(file_content, file.filename, "documents", file.content_type)
    if cloud_url:
        url_path = cloud_url
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        url_path = f"/uploads/{safe_filename}"
        
    _, ext = os.path.splitext(file.filename)
    file_type = ext.replace(".", "").upper() if ext else "UNKNOWN"
    
    doc_schema = schemas.DocumentBase(
        filename=file.filename,
        file_type=file_type,
        url_path=url_path
    )
    
    db.collection("projects").document(project_id).update({
        "updated_by": username,
        "updated_at": datetime.utcnow().isoformat()
    })
    
    db_doc = crud.create_document(db=db, document=doc_schema, project_id=project_id)
    crud.log_user_action(db, username, "สร้าง", "เอกสารแนบสัญญา", file.filename, f"อัปโหลดเอกสารแนบสัญญาโครงการ '{db_project.get('name')}'")
    return db_doc

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_doc = crud.get_document(db, document_id=document_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    url_path = db_doc.get("url_path")
    if url_path:
        delete_from_firebase_storage(url_path)
        filename = os.path.basename(url_path)
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
                
    project_id = db_doc.get("project_id")
    db_project = crud.get_project(db, project_id)
    if db_project:
        db.collection("projects").document(project_id).update({
            "updated_by": username,
            "updated_at": datetime.utcnow().isoformat()
        })
        
    crud.log_user_action(db, username, "ลบ", "เอกสารแนบสัญญา", db_doc.get("filename"), f"ลบเอกสารแนบสัญญาโครงการ '{db_project.get('name') if db_project else '-'}'")
    success = crud.delete_document(db=db, document_id=document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"detail": "Document deleted successfully"}


# Guarantee Receipt and Document Uploads
@app.post("/api/projects/{project_id}/guarantee-receipt", response_model=schemas.Project)
def upload_guarantee_receipt(
    project_id: str,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user_username),
    db = Depends(get_db)
):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    validate_uploaded_file(file)
    try:
        file_content = file.file.read()
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        
    cloud_url = upload_to_firebase_storage(file_content, file.filename, "guarantees", file.content_type)
    if cloud_url:
        guarantee_receipt_path = cloud_url
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_filename = f"guar_rec_{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        guarantee_receipt_path = f"/uploads/{safe_filename}"
        
    update_data = {
        "guarantee_receipt_path": guarantee_receipt_path,
        "guarantee_receipt_filename": file.filename,
        "updated_by": username,
        "updated_at": datetime.utcnow().isoformat()
    }
    db.collection("projects").document(project_id).update(update_data)
    db_project.update(update_data)
    
    crud.log_user_action(db, username, "สร้าง", "ใบเสร็จค้ำประกัน", file.filename, f"อัปโหลดหลักฐานใบเสร็จค้ำประกันโครงการ '{db_project.get('name')}'")
    return populate_project_relations(db, db_project)

@app.delete("/api/projects/{project_id}/guarantee-receipt", response_model=schemas.Project)
def delete_guarantee_receipt(project_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    receipt_path = db_project.get("guarantee_receipt_path")
    if receipt_path:
        delete_from_firebase_storage(receipt_path)
        filename = os.path.basename(receipt_path)
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
                
        orig_filename = db_project.get("guarantee_receipt_filename")
        update_data = {
            "guarantee_receipt_path": None,
            "guarantee_receipt_filename": None,
            "updated_by": username,
            "updated_at": datetime.utcnow().isoformat()
        }
        db.collection("projects").document(project_id).update(update_data)
        db_project.update(update_data)
        crud.log_user_action(db, username, "ลบ", "ใบเสร็จค้ำประกัน", orig_filename, f"ลบใบเสร็จค้ำประกันโครงการ '{db_project.get('name')}'")
    return populate_project_relations(db, db_project)

@app.post("/api/projects/{project_id}/guarantee-document", response_model=schemas.Project)
def upload_guarantee_document(
    project_id: str,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user_username),
    db = Depends(get_db)
):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    validate_uploaded_file(file)
    try:
        file_content = file.file.read()
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        
    cloud_url = upload_to_firebase_storage(file_content, file.filename, "guarantees", file.content_type)
    if cloud_url:
        guarantee_document_path = cloud_url
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_filename = f"guar_doc_{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        guarantee_document_path = f"/uploads/{safe_filename}"
        
    update_data = {
        "guarantee_document_path": guarantee_document_path,
        "guarantee_document_filename": file.filename,
        "updated_by": username,
        "updated_at": datetime.utcnow().isoformat()
    }
    db.collection("projects").document(project_id).update(update_data)
    db_project.update(update_data)
    
    crud.log_user_action(db, username, "สร้าง", "หลักฐานการค้ำประกัน", file.filename, f"อัปโหลดหลักฐานการค้ำประกันโครงการ '{db_project.get('name')}'")
    return populate_project_relations(db, db_project)

@app.delete("/api/projects/{project_id}/guarantee-document", response_model=schemas.Project)
def delete_guarantee_document(project_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    doc_path = db_project.get("guarantee_document_path")
    if doc_path:
        delete_from_firebase_storage(doc_path)
        filename = os.path.basename(doc_path)
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
                
        orig_filename = db_project.get("guarantee_document_filename")
        update_data = {
            "guarantee_document_path": None,
            "guarantee_document_filename": None,
            "updated_by": username,
            "updated_at": datetime.utcnow().isoformat()
        }
        db.collection("projects").document(project_id).update(update_data)
        db_project.update(update_data)
        crud.log_user_action(db, username, "ลบ", "หลักฐานการค้ำประกัน", orig_filename, f"ลบหลักฐานการค้ำประกันโครงการ '{db_project.get('name')}'")
    return populate_project_relations(db, db_project)


# Excel Export Endpoints
@app.get("/api/exports/projects/excel")
def export_projects_excel(query: Optional[str] = None, status: Optional[str] = None, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    try:
        projects = crud.get_projects(db, skip=0, limit=1000)
        filtered = []
        for p in projects:
            if status and status != "ทั้งหมด":
                if p.get("status") != status:
                    continue
            if query:
                q = query.lower()
                name_match = q in p.get("name", "").lower()
                owner_match = q in p.get("owner", "").lower()
                contractor_match = p.get("contractor") and (q in p.get("contractor").lower())
                job_type_match = p.get("job_type") and (q in p.get("job_type").lower())
                fiscal_year_match = p.get("fiscal_year") and (q in str(p.get("fiscal_year")))
                status_match = q in p.get("status", "").lower()
                if not (name_match or owner_match or contractor_match or job_type_match or fiscal_year_match or status_match):
                    continue
            filtered.append(p)
            
        excel_file = excel_export.export_projects_to_excel(filtered)
        headers = {
            'Content-Disposition': 'attachment; filename="projects_summary.xlsx"'
        }
        return StreamingResponse(excel_file, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error exporting projects Excel: {str(e)}")

@app.get("/api/exports/purchase-orders/excel")
def export_purchase_orders_excel(query: Optional[str] = None, status: Optional[str] = None, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    try:
        pos = crud.get_purchase_orders(db)
        filtered = []
        for po in pos:
            po = populate_po_project(db, po)
            if status and status != "ทั้งหมด":
                if po.get("delivery_status") != status:
                    continue
            if query:
                q = query.lower()
                project_info = po.get("project")
                proj_name = project_info.get("name", "").lower() if project_info else ""
                owner = project_info.get("owner", "").lower() if project_info else ""
                
                po_number_match = q in po.get("po_number", "").lower()
                proj_match = q in proj_name
                owner_match = q in owner
                contractor_match = q in po.get("contractor", "").lower()
                material_match = q in po.get("material_type", "").lower()
                if not (po_number_match or proj_match or owner_match or contractor_match or material_match):
                    continue
            filtered.append(po)
            
        excel_file = excel_export.export_purchase_orders_to_excel(filtered)
        headers = {
            'Content-Disposition': 'attachment; filename="purchase_orders_summary.xlsx"'
        }
        return StreamingResponse(excel_file, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error exporting purchase orders Excel: {str(e)}")

@app.get("/api/exports/projects/{project_id}/excel")
def export_project_detail_excel(project_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    try:
        project = crud.get_project(db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        project = populate_project_relations(db, project)
            
        excel_file = excel_export.export_project_detail_to_excel(project)
        headers = {
            'Content-Disposition': f'attachment; filename="project_detail_{project_id}.xlsx"'
        }
        return StreamingResponse(excel_file, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error exporting project detail Excel: {str(e)}")

@app.get("/api/exports/purchase-orders/{po_id}/excel")
def export_po_detail_excel(po_id: str, username: str = Depends(get_current_user_username), db = Depends(get_db)):
    try:
        po = crud.get_purchase_order(db, po_id=po_id)
        if not po:
            raise HTTPException(status_code=404, detail="Purchase Order not found")
        po = populate_po_project(db, po)
            
        excel_file = excel_export.export_po_detail_to_excel(po)
        headers = {
            'Content-Disposition': f'attachment; filename="purchase_order_detail_{po_id}.xlsx"'
        }
        return StreamingResponse(excel_file, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error exporting PO detail Excel: {str(e)}")


# Mount Static and Uploads directories
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Redirect root to /static/index.html
@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")
