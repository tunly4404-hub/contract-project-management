import os
from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import shutil
import jwt

import models
import schemas
import crud
from database import engine, get_db, SessionLocal
from typing import Optional
import excel_export

# Create DB tables
models.Base.metadata.create_all(bind=engine)

# Auto-migrate database fields if needed
def run_migrations():
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    
    # 1. Projects table
    try:
        columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'contract_duration_days' not in columns:
            print("Adding 'contract_duration_days' column to 'projects' table...")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE projects ADD COLUMN contract_duration_days INTEGER;"))
        if 'fiscal_year' not in columns:
            print("Adding 'fiscal_year' column to 'projects' table...")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE projects ADD COLUMN fiscal_year INTEGER;"))
    except Exception as e:
        print(f"Error migrating projects table: {e}")
        
    # 2. Deliverables table
    try:
        columns = [col['name'] for col in inspector.get_columns('deliverables')]
        if 'milestone' not in columns:
            print("Adding 'milestone' column to 'deliverables' table...")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE deliverables ADD COLUMN milestone TEXT;"))
        if 'budget' not in columns:
            print("Adding 'budget' column to 'deliverables' table...")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE deliverables ADD COLUMN budget FLOAT;"))
    except Exception as e:
        print(f"Error migrating deliverables table: {e}")

run_migrations()

# Auto-seed admin user if users table is empty (V5 RBAC Render helper)
def auto_seed_db():
    db = SessionLocal()
    try:
        admin_user = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin_user:
            print("Auto-seeding default admin account on startup...")
            admin_schema = schemas.UserCreate(
                username="admin",
                fullname="ผู้ดูแลระบบหลัก",
                role="admin",
                password="admin1234" # As requested by user: admin1234
            )
            crud.create_user(db, admin_schema)
            # Enforce admin role and active status
            db_admin = db.query(models.User).filter(models.User.username == "admin").first()
            if db_admin:
                db_admin.role = "admin"
                db_admin.is_active = True
                db.commit()
                
        sittipan_user = db.query(models.User).filter(models.User.username == "sittipan").first()
        if not sittipan_user:
            sittipan_schema = schemas.UserCreate(
                username="sittipan",
                fullname="คุณ สิทธิพรรณ",
                role="user",
                password="sittipan123"
            )
            crud.create_user(db, sittipan_schema)
            db_sittipan = db.query(models.User).filter(models.User.username == "sittipan").first()
            if db_sittipan:
                db_sittipan.role = "user"
                db_sittipan.is_active = True
                db.commit()
    except Exception as e:
        print(f"Error during auto-seeding: {e}")
    finally:
        db.close()

auto_seed_db()

# Support persistent directory (e.g. Render Disk mounted at /data)
PERSISTENT_DIR = "/data" if os.path.exists("/data") and os.path.isdir("/data") else "."

UPLOAD_DIR = os.path.join(PERSISTENT_DIR, "uploads")
UPLOAD_PO_DIR = os.path.join(UPLOAD_DIR, "pos")
UPLOAD_DELIVERY_DIR = os.path.join(UPLOAD_DIR, "deliveries")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(UPLOAD_PO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DELIVERY_DIR, exist_ok=True)
os.makedirs("./static", exist_ok=True)

app = FastAPI(title="ระบบบริหารจัดการสัญญาและโครงการ (Project & Contract Management)")

# JWT configuration
SECRET_KEY = "ANTIGRAVITY_V5_SECRET_KEY_JWT_SECURITY_HASH"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 180

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

def get_current_user_username(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="บัญชีผู้ใช้งานนี้ยังไม่ได้รับการอนุมัติจากผู้ดูแลระบบ (Admin) หรือถูกระงับสิทธิ์เข้าใช้งาน กรุณาติดต่อผู้ดูแลระบบเพื่ออนุมัติสิทธิ์เข้าใช้งาน",
        )
    return user.username

def check_admin_role(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = get_current_user_username(token, db)
    user = crud.get_user_by_username(db, username=username)
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


# Authentication Routes
@app.post("/api/auth/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.post("/api/auth/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=user_credentials.username)
    if not user or not crud.verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    if not user.is_active:
        raise HTTPException(
            status_code=400, 
            detail="บัญชีผู้ใช้งานนี้ยังไม่ได้รับการอนุมัติจากผู้ดูแลระบบ (Admin) หรือถูกระงับสิทธิ์เข้าใช้งาน กรุณาติดต่อผู้ดูแลระบบเพื่ออนุมัติสิทธิ์เข้าใช้งาน"
        )
        
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@app.get("/api/auth/me", response_model=schemas.UserResponse)
def get_me(username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# User Management Endpoints (Admin Only)
@app.get("/api/users", response_model=List[schemas.UserResponse])
def get_all_users(current_admin = Depends(check_admin_role), db: Session = Depends(get_db)):
    return db.query(models.User).all()

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, current_admin = Depends(check_admin_role), db: Session = Depends(get_db)):
    if current_admin.id == user_id:
        raise HTTPException(status_code=400, detail="ไม่สามารถลบบัญชีผู้ใช้งานของตนเองได้")
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้งานในระบบ")
        
    db.delete(db_user)
    db.commit()
    return {"detail": "User deleted successfully"}

@app.put("/api/users/{user_id}/toggle-active", response_model=schemas.UserResponse)
def toggle_user_active(user_id: int, current_admin = Depends(check_admin_role), db: Session = Depends(get_db)):
    if current_admin.id == user_id:
        raise HTTPException(status_code=400, detail="ไม่สามารถระงับสิทธิ์บัญชีผู้ใช้งานของตนเองได้")
        
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้งานในระบบ")
        
    db_user.is_active = not db_user.is_active
    db.commit()
    db.refresh(db_user)
    return db_user

@app.put("/api/users/{user_id}/reset-password")
def reset_user_password(user_id: int, payload: schemas.UserResetPassword, current_admin = Depends(check_admin_role), db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้งานในระบบ")
        
    db_user.hashed_password = crud.get_password_hash(payload.new_password)
    db.commit()
    return {"detail": f"เปลี่ยนรหัสผ่านสำหรับผู้ใช้งาน {db_user.username} เรียบร้อยแล้ว"}

@app.get("/api/admin/disk-usage")
def get_disk_usage(current_admin = Depends(check_admin_role)):
    import shutil
    import os
    persistent_dir = "/data" if os.path.exists("/data") and os.path.isdir("/data") else "."
    try:
        total, used, free = shutil.disk_usage(persistent_dir)
        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "percentage_used": round((used / total) * 100, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read disk usage: {str(e)}")

@app.get("/api/audit-logs", response_model=List[schemas.AuditLogResponse])
def get_audit_logs(
    username: str = Depends(get_current_user_username),
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.role == "admin":
        return db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).all()
    else:
        return db.query(models.AuditLog).filter(models.AuditLog.username == username).order_by(models.AuditLog.timestamp.desc()).all()


# Dashboard Endpoints (Secured)
@app.get("/api/dashboard/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    return crud.get_dashboard_stats(db)

@app.get("/api/dashboard/alerts", response_model=List[schemas.DashboardAlert])
def get_dashboard_alerts(username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    return crud.get_dashboard_alerts(db)

@app.get("/api/dashboard/po-alerts", response_model=List[schemas.DashboardPOAlert])
def get_dashboard_po_alerts(username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    return crud.get_dashboard_po_alerts(db)


# Project Endpoints (Secured)
@app.get("/api/projects", response_model=List[schemas.Project])
def read_projects(skip: int = 0, limit: int = 100, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    return crud.get_projects(db, skip=skip, limit=limit)

@app.get("/api/projects/{project_id}", response_model=schemas.Project)
def read_project(project_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return db_project

@app.post("/api/projects", response_model=schemas.Project)
def create_project(project: schemas.ProjectCreate, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_project = crud.create_project(db=db, project=project, username=username)
    crud.log_user_action(db, username, "สร้าง", "โครงการ", db_project.name, f"งบประมาณ: {db_project.budget} บาท")
    return db_project

@app.put("/api/projects/{project_id}", response_model=schemas.Project)
def update_project(project_id: int, project: schemas.ProjectUpdate, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_project_old = crud.get_project(db, project_id)
    if not db_project_old:
        raise HTTPException(status_code=404, detail="Project not found")
    db_project = crud.update_project(db=db, project_id=project_id, project=project, username=username)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    crud.log_user_action(db, username, "แก้ไข", "โครงการ", db_project.name, "แก้ไขข้อมูลโครงการ")
    return db_project

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, current_admin = Depends(check_admin_role), db: Session = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    crud.log_user_action(db, current_admin.username, "ลบ", "โครงการ", db_project.name, f"ลบโครงการ ID: {project_id}")
    success = crud.delete_project(db=db, project_id=project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"detail": "Project deleted successfully"}


# Deliverables Endpoints (Secured)
@app.post("/api/projects/{project_id}/deliverables", response_model=schemas.Deliverable)
def create_project_deliverable(project_id: int, deliverable: schemas.DeliverableCreate, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    db_deliverable = crud.create_deliverable(db=db, deliverable=deliverable, project_id=project_id, username=username)
    crud.log_user_action(db, username, "สร้าง", "งวดงานสัญญาหลัก", db_deliverable.name, f"สร้างงวดงานในโครงการ '{db_project.name}'")
    return db_deliverable

@app.put("/api/deliverables/{deliverable_id}", response_model=schemas.Deliverable)
def update_deliverable(deliverable_id: int, deliverable: schemas.DeliverableUpdate, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_del = db.query(models.Deliverable).filter(models.Deliverable.id == deliverable_id).first()
    if not db_del:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    db_deliverable = crud.update_deliverable(db=db, deliverable_id=deliverable_id, deliverable=deliverable, username=username)
    crud.log_user_action(db, username, "แก้ไข", "งวดงานสัญญาหลัก", db_deliverable.name, f"แก้ไขรายละเอียดงวดงาน (สถานะ: {db_deliverable.status})")
    return db_deliverable

@app.delete("/api/deliverables/{deliverable_id}")
def delete_deliverable(deliverable_id: int, current_admin = Depends(check_admin_role), db: Session = Depends(get_db)):
    db_del = db.query(models.Deliverable).filter(models.Deliverable.id == deliverable_id).first()
    if not db_del:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    crud.log_user_action(db, current_admin.username, "ลบ", "งวดงานสัญญาหลัก", db_del.name, f"ลบงวดงาน ID: {deliverable_id}")
    success = crud.delete_deliverable(db=db, deliverable_id=deliverable_id)
    if not success:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    return {"detail": "Deliverable deleted successfully"}


# Purchase Order (PO) Endpoints (Secured V4)
@app.get("/api/purchase-orders", response_model=List[schemas.PurchaseOrder])
def read_purchase_orders(username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    return crud.get_purchase_orders(db)

@app.get("/api/purchase-orders/{po_id}", response_model=schemas.PurchaseOrder)
def read_purchase_order(po_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    return db_po

@app.post("/api/projects/{project_id}/purchase-orders", response_model=schemas.PurchaseOrder)
def create_purchase_order(project_id: int, po: schemas.PurchaseOrderCreate, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    db_po = crud.create_purchase_order(db=db, po=po, project_id=project_id, username=username)
    crud.log_user_action(db, username, "สร้าง", "ใบสั่งซื้อ PO", db_po.po_number, f"สร้างใบสั่งซื้อ PO งบประมาณ: {db_po.budget} บาท ในโครงการ '{db_project.name}'")
    return db_po

@app.put("/api/purchase-orders/{po_id}", response_model=schemas.PurchaseOrder)
def update_purchase_order(po_id: int, po: schemas.PurchaseOrderUpdate, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_po_old = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not db_po_old:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    old_delivery_status = db_po_old.delivery_status
    
    db_po = crud.update_purchase_order(db=db, po_id=po_id, po=po, username=username)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    if old_delivery_status != db_po.delivery_status:
        crud.log_user_action(db, username, "แก้ไข", "ใบส่งมอบของ", f"PO: {db_po.po_number}", f"ปรับปรุงการส่งมอบเป็น '{db_po.delivery_status}' (เลขที่ใบส่งของ: {db_po.delivery_no or '-'})")
    else:
        crud.log_user_action(db, username, "แก้ไข", "ใบสั่งซื้อ PO", db_po.po_number, "แก้ไขรายละเอียดใบสั่งซื้อ")
    return db_po

@app.delete("/api/purchase-orders/{po_id}")
def delete_purchase_order(po_id: int, current_admin = Depends(check_admin_role), db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    for path in [db_po.po_file_path, db_po.quotation_file_path, db_po.delivery_file_path]:
        if path:
            filename = os.path.basename(path)
            for folder in [UPLOAD_PO_DIR, UPLOAD_DELIVERY_DIR, UPLOAD_DIR]:
                file_path = os.path.join(folder, filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        break
                    except Exception:
                        pass
                        
    crud.log_user_action(db, current_admin.username, "ลบ", "ใบสั่งซื้อ PO", db_po.po_number, f"ลบใบสั่งซื้อ ID: {po_id}")
    success = crud.delete_purchase_order(db=db, po_id=po_id)
    if not success:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    return {"detail": "Purchase Order deleted successfully"}


# PO Document Files Upload (Secured V4)
@app.post("/api/purchase-orders/{po_id}/po-file", response_model=schemas.PurchaseOrder)
def upload_po_file(po_id: int, file: UploadFile = File(...), username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    validate_uploaded_file(file)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_filename = f"po_{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_PO_DIR, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    db_po.po_file_path = f"/uploads/pos/{safe_filename}"
    db_po.po_file_filename = file.filename
    db_po.updated_by = username
    db_po.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_po)
    crud.log_user_action(db, username, "สร้าง", "ไฟล์ใบสั่งซื้อ PO", file.filename, f"อัปโหลดไฟล์ใบสั่งซื้อสำหรับ PO: {db_po.po_number}")
    return db_po

@app.delete("/api/purchase-orders/{po_id}/po-file", response_model=schemas.PurchaseOrder)
def delete_po_file(po_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    if db_po.po_file_path:
        filename = os.path.basename(db_po.po_file_path)
        file_path = os.path.join(UPLOAD_PO_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        orig_filename = db_po.po_file_filename
        db_po.po_file_path = None
        db_po.po_file_filename = None
        db_po.updated_by = username
        db_po.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_po)
        crud.log_user_action(db, username, "ลบ", "ไฟล์ใบสั่งซื้อ PO", orig_filename, f"ลบไฟล์ใบสั่งซื้อสำหรับ PO: {db_po.po_number}")
    return db_po

@app.post("/api/purchase-orders/{po_id}/quotation-file", response_model=schemas.PurchaseOrder)
def upload_quotation_file(po_id: int, file: UploadFile = File(...), username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    validate_uploaded_file(file)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_filename = f"quot_{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_PO_DIR, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    db_po.quotation_file_path = f"/uploads/pos/{safe_filename}"
    db_po.quotation_file_filename = file.filename
    db_po.updated_by = username
    db_po.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_po)
    crud.log_user_action(db, username, "สร้าง", "ไฟล์ใบเสนอราคา PO", file.filename, f"อัปโหลดไฟล์ใบเสนอราคาสำหรับ PO: {db_po.po_number}")
    return db_po

@app.delete("/api/purchase-orders/{po_id}/quotation-file", response_model=schemas.PurchaseOrder)
def delete_quotation_file(po_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    if db_po.quotation_file_path:
        filename = os.path.basename(db_po.quotation_file_path)
        file_path = os.path.join(UPLOAD_PO_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        orig_filename = db_po.quotation_file_filename
        db_po.quotation_file_path = None
        db_po.quotation_file_filename = None
        db_po.updated_by = username
        db_po.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_po)
        crud.log_user_action(db, username, "ลบ", "ไฟล์ใบเสนอราคา PO", orig_filename, f"ลบไฟล์ใบเสนอราคาสำหรับ PO: {db_po.po_number}")
    return db_po


# PO Delivery File Upload (Secured V4)
@app.post("/api/purchase-orders/{po_id}/delivery-file", response_model=schemas.PurchaseOrder)
def upload_delivery_file(po_id: int, file: UploadFile = File(...), username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    validate_uploaded_file(file)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_filename = f"delivery_{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DELIVERY_DIR, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    db_po.delivery_file_path = f"/uploads/deliveries/{safe_filename}"
    db_po.delivery_file_filename = file.filename
    db_po.updated_by = username
    db_po.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_po)
    crud.log_user_action(db, username, "สร้าง", "ไฟล์ใบส่งของ PO", file.filename, f"อัปโหลดไฟล์ใบส่งของสำหรับ PO: {db_po.po_number}")
    return db_po

@app.delete("/api/purchase-orders/{po_id}/delivery-file", response_model=schemas.PurchaseOrder)
def delete_delivery_file(po_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order(db, po_id=po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    if db_po.delivery_file_path:
        filename = os.path.basename(db_po.delivery_file_path)
        file_path = os.path.join(UPLOAD_DELIVERY_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        orig_filename = db_po.delivery_file_filename
        db_po.delivery_file_path = None
        db_po.delivery_file_filename = None
        db_po.updated_by = username
        db_po.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_po)
        crud.log_user_action(db, username, "ลบ", "ไฟล์ใบส่งของ PO", orig_filename, f"ลบไฟล์ใบส่งของสำหรับ PO: {db_po.po_number}")
    return db_po


# Contract Documents (Secured)
@app.post("/api/projects/{project_id}/documents", response_model=schemas.Document)
def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user_username),
    db: Session = Depends(get_db)
):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    _, ext = os.path.splitext(file.filename)
    file_type = ext.replace(".", "").upper() if ext else "UNKNOWN"
    url_path = f"/uploads/{safe_filename}"
    
    doc_schema = schemas.DocumentBase(
        filename=file.filename,
        file_type=file_type,
        url_path=url_path
    )
    
    db_project.updated_by = username
    db_project.updated_at = datetime.utcnow()
    db.commit()
    
    db_doc = crud.create_document(db=db, document=doc_schema, project_id=project_id)
    crud.log_user_action(db, username, "สร้าง", "เอกสารสัญญา", file.filename, f"อัปโหลดไฟล์เอกสารสัญญาในโครงการ '{db_project.name}'")
    return db_doc

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_doc = crud.get_document(db, document_id=document_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    filename = os.path.basename(db_doc.url_path)
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
            
    # Update project audit
    db_project = crud.get_project(db, db_doc.project_id)
    if db_project:
        db_project.updated_by = username
        db_project.updated_at = datetime.utcnow()
        db.commit()
            
    orig_filename = db_doc.filename
    success = crud.delete_document(db=db, document_id=document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    crud.log_user_action(db, username, "ลบ", "เอกสารสัญญา", orig_filename, f"ลบไฟล์เอกสารสัญญาออกจากระบบ")
    return {"detail": "Document deleted successfully"}


# Guarantee Receipt (Secured)
@app.post("/api/projects/{project_id}/guarantee-receipt", response_model=schemas.Project)
def upload_guarantee_receipt(
    project_id: int,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user_username),
    db: Session = Depends(get_db)
):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    validate_uploaded_file(file)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_filename = f"receipt_{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    db_project.guarantee_receipt_path = f"/uploads/{safe_filename}"
    db_project.guarantee_receipt_filename = file.filename
    db_project.updated_by = username
    db_project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_project)
    crud.log_user_action(db, username, "สร้าง", "ใบเสร็จค้ำประกัน", file.filename, f"อัปโหลดใบเสร็จค้ำประกันโครงการ '{db_project.name}'")
    return db_project

@app.delete("/api/projects/{project_id}/guarantee-receipt", response_model=schemas.Project)
def delete_guarantee_receipt(project_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if db_project.guarantee_receipt_path:
        filename = os.path.basename(db_project.guarantee_receipt_path)
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        orig_filename = db_project.guarantee_receipt_filename
        db_project.guarantee_receipt_path = None
        db_project.guarantee_receipt_filename = None
        db_project.updated_by = username
        db_project.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_project)
        crud.log_user_action(db, username, "ลบ", "ใบเสร็จค้ำประกัน", orig_filename, f"ลบใบเสร็จค้ำประกันโครงการ '{db_project.name}'")
    return db_project


# Guarantee Document - LG / Slip (Secured)
@app.post("/api/projects/{project_id}/guarantee-document", response_model=schemas.Project)
def upload_guarantee_document(
    project_id: int,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user_username),
    db: Session = Depends(get_db)
):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    validate_uploaded_file(file)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_filename = f"guar_doc_{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    db_project.guarantee_document_path = f"/uploads/{safe_filename}"
    db_project.guarantee_document_filename = file.filename
    db_project.updated_by = username
    db_project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_project)
    crud.log_user_action(db, username, "สร้าง", "หลักฐานการค้ำประกัน", file.filename, f"อัปโหลดหลักฐานการค้ำประกันโครงการ '{db_project.name}'")
    return db_project

@app.delete("/api/projects/{project_id}/guarantee-document", response_model=schemas.Project)
def delete_guarantee_document(project_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if db_project.guarantee_document_path:
        filename = os.path.basename(db_project.guarantee_document_path)
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        orig_filename = db_project.guarantee_document_filename
        db_project.guarantee_document_path = None
        db_project.guarantee_document_filename = None
        db_project.updated_by = username
        db_project.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_project)
        crud.log_user_action(db, username, "ลบ", "หลักฐานการค้ำประกัน", orig_filename, f"ลบหลักฐานการค้ำประกันโครงการ '{db_project.name}'")
    return db_project


# Excel Export Endpoints
@app.get("/api/exports/projects/excel")
def export_projects_excel(query: Optional[str] = None, status: Optional[str] = None, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    try:
        projects = crud.get_projects(db, skip=0, limit=1000)
        filtered = []
        for p in projects:
            if status and status != "ทั้งหมด":
                if p.status != status:
                    continue
            if query:
                q = query.lower()
                name_match = q in p.name.lower()
                owner_match = q in p.owner.lower()
                contractor_match = p.contractor and (q in p.contractor.lower())
                job_type_match = p.job_type and (q in p.job_type.lower())
                fiscal_year_match = p.fiscal_year and (q in str(p.fiscal_year))
                status_match = q in p.status.lower()
                if not (name_match or owner_match or contractor_match or job_type_match or fiscal_year_match or status_match):
                    continue
            filtered.append(p)
            
        excel_file = excel_export.export_projects_to_excel(filtered)
        
        from fastapi.responses import StreamingResponse
        headers = {
            'Content-Disposition': 'attachment; filename="projects_summary.xlsx"'
        }
        return StreamingResponse(excel_file, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error exporting projects Excel: {str(e)}")

@app.get("/api/exports/purchase-orders/excel")
def export_purchase_orders_excel(query: Optional[str] = None, status: Optional[str] = None, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    try:
        pos = crud.get_purchase_orders(db, skip=0, limit=1000)
        filtered = []
        for po in pos:
            if status and status != "ทั้งหมด":
                if po.delivery_status != status:
                    continue
            if query:
                q = query.lower()
                proj_name = po.project.name.lower() if po.project else ""
                owner = po.project.owner.lower() if po.project else ""
                po_number_match = q in po.po_number.lower()
                proj_match = q in proj_name
                owner_match = q in owner
                contractor_match = q in po.contractor.lower()
                material_match = q in po.material_type.lower()
                if not (po_number_match or proj_match or owner_match or contractor_match or material_match):
                    continue
            filtered.append(po)
            
        excel_file = excel_export.export_purchase_orders_to_excel(filtered)
        
        from fastapi.responses import StreamingResponse
        headers = {
            'Content-Disposition': 'attachment; filename="purchase_orders_summary.xlsx"'
        }
        return StreamingResponse(excel_file, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error exporting purchase orders Excel: {str(e)}")

@app.get("/api/exports/projects/{project_id}/excel")
def export_project_detail_excel(project_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    try:
        project = crud.get_project(db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        excel_file = excel_export.export_project_detail_to_excel(project)
        
        from fastapi.responses import StreamingResponse
        headers = {
            'Content-Disposition': f'attachment; filename="project_detail_{project_id}.xlsx"'
        }
        return StreamingResponse(excel_file, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error exporting project detail Excel: {str(e)}")

@app.get("/api/exports/purchase-orders/{po_id}/excel")
def export_po_detail_excel(po_id: int, username: str = Depends(get_current_user_username), db: Session = Depends(get_db)):
    try:
        po = crud.get_purchase_order(db, po_id=po_id)
        if not po:
            raise HTTPException(status_code=404, detail="Purchase Order not found")
            
        excel_file = excel_export.export_po_detail_to_excel(po)
        
        from fastapi.responses import StreamingResponse
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
