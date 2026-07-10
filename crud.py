from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
import bcrypt
import models
import schemas

# User operations (V5)
def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_byte_enc = plain_password.encode('utf-8')
    hashed_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_byte_enc)

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_pwd = get_password_hash(user.password)
    first_user = db.query(models.User).first()
    role_val = "admin" if first_user is None else "user"
    db_user = models.User(
        username=user.username,
        fullname=user.fullname,
        role=role_val,
        is_active=True,
        hashed_password=hashed_pwd
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# Project CRUD with V5 Audit Trail
def get_project(db: Session, project_id: int):
    return db.query(models.Project).filter(models.Project.id == project_id).first()

def get_projects(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Project).offset(skip).limit(limit).all()

def create_project(db: Session, project: schemas.ProjectCreate, username: str):
    project_dict = project.model_dump()
    # Remove audit keys to prevent duplicate keyword arguments
    for f in ["created_by", "created_at", "updated_by", "updated_at"]:
        project_dict.pop(f, None)
        
    db_project = models.Project(
        created_by=username,
        updated_by=username,
        **project_dict
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def update_project(db: Session, project_id: int, project: schemas.ProjectUpdate, username: str):
    db_project = get_project(db, project_id)
    if not db_project:
        return None
    
    update_data = project.model_dump(exclude_unset=True)
    # Prevent user payload from manually overwriting audit trail metadata
    for f in ["created_by", "created_at", "updated_by", "updated_at"]:
        update_data.pop(f, None)
        
    for key, value in update_data.items():
        setattr(db_project, key, value)
        
    db_project.updated_by = username
    db_project.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id: int):
    db_project = get_project(db, project_id)
    if not db_project:
        return False
    db.delete(db_project)
    db.commit()
    return True


# Deliverable CRUD with V5 Audit Trail
def get_deliverable(db: Session, deliverable_id: int):
    return db.query(models.Deliverable).filter(models.Deliverable.id == deliverable_id).first()

def create_deliverable(db: Session, deliverable: schemas.DeliverableCreate, project_id: int, username: str):
    del_dict = deliverable.model_dump()
    for f in ["created_by", "created_at", "updated_by", "updated_at"]:
        del_dict.pop(f, None)
        
    db_deliverable = models.Deliverable(
        project_id=project_id,
        created_by=username,
        updated_by=username,
        **del_dict
    )
    db.add(db_deliverable)
    db.commit()
    db.refresh(db_deliverable)
    return db_deliverable

def update_deliverable(db: Session, deliverable_id: int, deliverable: schemas.DeliverableUpdate, username: str):
    db_deliverable = get_deliverable(db, deliverable_id)
    if not db_deliverable:
        return None
    
    update_data = deliverable.model_dump(exclude_unset=True)
    for f in ["created_by", "created_at", "updated_by", "updated_at"]:
        update_data.pop(f, None)
        
    for key, value in update_data.items():
        setattr(db_deliverable, key, value)
        
    db_deliverable.updated_by = username
    db_deliverable.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_deliverable)
    return db_deliverable

def delete_deliverable(db: Session, deliverable_id: int):
    db_deliverable = get_deliverable(db, deliverable_id)
    if not db_deliverable:
        return False
    db.delete(db_deliverable)
    db.commit()
    return True


# Document CRUD
def get_document(db: Session, document_id: int):
    return db.query(models.Document).filter(models.Document.id == document_id).first()

def create_document(db: Session, document: schemas.DocumentBase, project_id: int):
    db_document = models.Document(
        project_id=project_id,
        filename=document.filename,
        file_type=document.file_type,
        url_path=document.url_path
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

def delete_document(db: Session, document_id: int):
    db_document = get_document(db, document_id)
    if not db_document:
        return False
    db.delete(db_document)
    db.commit()
    return True


# Dashboard functions
def get_dashboard_stats(db: Session):
    projects = db.query(models.Project).all()
    total_projects = len(projects)
    
    status_counts = {
        "กำลังดำเนินการ": 0,
        "ล่าช้า": 0,
        "ส่งมอบแล้ว": 0
    }
    
    active_budget = 0.0
    for p in projects:
        if p.status in status_counts:
            status_counts[p.status] += 1
        else:
            status_counts[p.status] = status_counts.get(p.status, 0) + 1
            
        if p.status == "กำลังดำเนินการ":
            active_budget += p.budget
            
    return {
        "total_projects": total_projects,
        "projects_by_status": status_counts,
        "active_total_budget": active_budget
    }

def get_dashboard_alerts(db: Session):
    today = date.today()
    target_date = today + timedelta(days=14)
    
    # query deliverables that are pending ("รอดำเนินการ") and due in 14 days
    deliverables = db.query(models.Deliverable).filter(
        models.Deliverable.status == "รอดำเนินการ",
        models.Deliverable.due_date <= target_date
    ).order_by(models.Deliverable.due_date.asc()).all()
    
    alerts = []
    for d in deliverables:
        project = db.query(models.Project).filter(models.Project.id == d.project_id).first()
        if not project:
            continue
            
        days_remaining = (d.due_date - today).days
        alerts.append({
            "deliverable_id": d.id,
            "project_id": d.project_id,
            "project_name": project.name,
            "deliverable_name": d.name,
            "due_date": d.due_date,
            "days_remaining": days_remaining,
            "status": d.status
        })
        
    return alerts


# Purchase Order CRUD (V4) with V5 Audit Trail
def get_purchase_order(db: Session, po_id: int):
    return db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()

def get_purchase_orders(db: Session):
    return db.query(models.PurchaseOrder).all()

def create_purchase_order(db: Session, po: schemas.PurchaseOrderCreate, project_id: int, username: str):
    po_dict = po.model_dump()
    for f in ["created_by", "created_at", "updated_by", "updated_at"]:
        po_dict.pop(f, None)
        
    db_po = models.PurchaseOrder(
        project_id=project_id,
        created_by=username,
        updated_by=username,
        **po_dict
    )
    db.add(db_po)
    db.commit()
    db.refresh(db_po)
    return db_po

def update_purchase_order(db: Session, po_id: int, po: schemas.PurchaseOrderUpdate, username: str):
    db_po = get_purchase_order(db, po_id)
    if not db_po:
        return None
    
    update_data = po.model_dump(exclude_unset=True)
    for f in ["created_by", "created_at", "updated_by", "updated_at"]:
        update_data.pop(f, None)
        
    for key, value in update_data.items():
        setattr(db_po, key, value)
        
    db_po.updated_by = username
    db_po.updated_at = datetime.utcnow()
        
    db.commit()
    db.refresh(db_po)
    return db_po

def delete_purchase_order(db: Session, po_id: int):
    db_po = get_purchase_order(db, po_id)
    if not db_po:
        return False
    db.delete(db_po)
    db.commit()
    return True

def get_dashboard_po_alerts(db: Session):
    today = date.today()
    pos = db.query(models.PurchaseOrder).filter(
        models.PurchaseOrder.delivery_status == "ยังไม่ได้ส่ง"
    ).all()
    
    alerts = []
    for po in pos:
        days_remaining = (po.due_date - today).days
        if days_remaining <= 7:
            project = db.query(models.Project).filter(models.Project.id == po.project_id).first()
            project_name = project.name if project else "ไม่พบโครงการ"
            alerts.append({
                "po_id": po.id,
                "project_id": po.project_id,
                "project_name": project_name,
                "po_number": po.po_number,
                "budget": po.budget,
                "due_date": po.due_date,
                "days_remaining": days_remaining,
                "delivery_status": po.delivery_status
            })
            
    alerts.sort(key=lambda x: x["days_remaining"])
    return alerts

def log_user_action(db: Session, username: str, action: str, target_type: str, target_name: str, details: str = None):
    user = db.query(models.User).filter(models.User.username == username).first()
    user_id = user.id if user else None
    fullname = user.fullname if user else None
    
    db_log = models.AuditLog(
        user_id=user_id,
        username=username,
        fullname=fullname,
        action=action,
        target_type=target_type,
        target_name=target_name,
        details=details
    )
    db.add(db_log)
    db.commit()
    return db_log
