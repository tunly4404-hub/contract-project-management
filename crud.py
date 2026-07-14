from datetime import date, timedelta, datetime
import bcrypt
import schemas

# User operations password helpers
def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_byte_enc = plain_password.encode('utf-8')
    hashed_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_byte_enc)

def get_user_by_username(db, username: str):
    if db is None or not username:
        return None
    doc = db.collection("users").document(username).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None

def create_user(db, user: schemas.UserCreate):
    if db is None:
        return None
    hashed_pwd = get_password_hash(user.password)
    
    # Check if this is the first user to make them admin
    users_ref = db.collection("users")
    first_user = next(users_ref.limit(1).stream(), None)
    role_val = "admin" if first_user is None else "user"
    
    user_data = {
        "username": user.username.strip(),
        "fullname": user.fullname.strip(),
        "role": role_val,
        "is_active": False,  # Approval needed from admin
        "hashed_password": hashed_pwd,
        "company": user.company.strip() if user.company else None
    }
    
    users_ref.document(user.username.strip()).set(user_data)
    user_data["id"] = user.username.strip()
    return user_data


# Project CRUD
def get_project(db, project_id: str):
    if db is None or not project_id:
        return None
    doc = db.collection("projects").document(project_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None

def get_projects(db, skip: int = 0, limit: int = 100, contractor: str = None):
    if db is None:
        return []
        
    query = db.collection("projects")
    if contractor:
        query = query.where("contractor", "==", contractor)
        
    docs = query.stream()
    projects = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        projects.append(data)
    
    # Sort projects: oldest first
    def get_sort_key(item):
        created_at = item.get("created_at")
        if created_at:
            return str(created_at)
        signing_date = item.get("contract_signing_date")
        if signing_date:
            return str(signing_date)
        return item.get("id", "")
    
    projects.sort(key=get_sort_key)
    return projects[skip:skip+limit]

def create_project(db, project: schemas.ProjectCreate, username: str):
    if db is None:
        return None
    project_dict = project.model_dump()
    for k, v in project_dict.items():
        if isinstance(v, (date, datetime)):
            project_dict[k] = v.isoformat()
            
    project_dict["created_by"] = username
    project_dict["created_at"] = datetime.utcnow().isoformat()
    project_dict["updated_by"] = username
    project_dict["updated_at"] = datetime.utcnow().isoformat()
    
    doc_ref = db.collection("projects").document()
    doc_ref.set(project_dict)
    
    project_dict["id"] = doc_ref.id
    return project_dict

def update_project(db, project_id: str, project: schemas.ProjectUpdate, username: str):
    if db is None or not project_id:
        return None
    db_project = get_project(db, project_id)
    if not db_project:
        return None
        
    update_data = project.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if isinstance(v, (date, datetime)):
            update_data[k] = v.isoformat()
            
    for f in ["created_by", "created_at", "updated_by", "updated_at", "id"]:
        update_data.pop(f, None)
        
    update_data["updated_by"] = username
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    db.collection("projects").document(project_id).update(update_data)
    return get_project(db, project_id)

def delete_project(db, project_id: str):
    if db is None or not project_id:
        return False
    
    # Delete the project document
    db.collection("projects").document(project_id).delete()
    
    # Cascade delete associated deliverables
    delivs = db.collection("deliverables").where("project_id", "==", project_id).stream()
    for d in delivs:
        d.reference.delete()
        
    # Cascade delete associated purchase orders
    pos = db.collection("purchase_orders").where("project_id", "==", project_id).stream()
    for po in pos:
        po.reference.delete()
        
    # Cascade delete associated documents
    docs = db.collection("documents").where("project_id", "==", project_id).stream()
    for d in docs:
        d.reference.delete()
        
    return True


# Deliverables CRUD
def get_deliverable(db, deliverable_id: str):
    if db is None or not deliverable_id:
        return None
    doc = db.collection("deliverables").document(deliverable_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None

def create_deliverable(db, deliverable: schemas.DeliverableCreate, project_id: str, username: str):
    if db is None:
        return None
    deliv_dict = deliverable.model_dump()
    for k, v in deliv_dict.items():
        if isinstance(v, (date, datetime)):
            deliv_dict[k] = v.isoformat()
            
    deliv_dict["project_id"] = project_id
    deliv_dict["created_by"] = username
    deliv_dict["created_at"] = datetime.utcnow().isoformat()
    deliv_dict["updated_by"] = username
    deliv_dict["updated_at"] = datetime.utcnow().isoformat()
    
    doc_ref = db.collection("deliverables").document()
    doc_ref.set(deliv_dict)
    
    deliv_dict["id"] = doc_ref.id
    return deliv_dict

def update_deliverable(db, deliverable_id: str, deliverable: schemas.DeliverableUpdate, username: str):
    if db is None or not deliverable_id:
        return None
    db_deliv = get_deliverable(db, deliverable_id)
    if not db_deliv:
        return None
        
    update_data = deliverable.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if isinstance(v, (date, datetime)):
            update_data[k] = v.isoformat()
            
    for f in ["created_by", "created_at", "updated_by", "updated_at", "id", "project_id"]:
        update_data.pop(f, None)
        
    update_data["updated_by"] = username
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    db.collection("deliverables").document(deliverable_id).update(update_data)
    return get_deliverable(db, deliverable_id)

def delete_deliverable(db, deliverable_id: str):
    if db is None or not deliverable_id:
        return False
    db.collection("deliverables").document(deliverable_id).delete()
    return True


# Document CRUD
def get_document(db, document_id: str):
    if db is None or not document_id:
        return None
    doc = db.collection("documents").document(document_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None

def create_document(db, document: schemas.DocumentBase, project_id: str):
    if db is None:
        return None
    doc_dict = {
        "project_id": project_id,
        "filename": document.filename,
        "file_type": document.file_type,
        "url_path": document.url_path
    }
    doc_ref = db.collection("documents").document()
    doc_ref.set(doc_dict)
    doc_dict["id"] = doc_ref.id
    return doc_dict

def delete_document(db, document_id: str):
    if db is None or not document_id:
        return False
    db.collection("documents").document(document_id).delete()
    return True


# Purchase Order CRUD
def get_purchase_order(db, po_id: str):
    if db is None or not po_id:
        return None
    doc = db.collection("purchase_orders").document(po_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None

def get_purchase_orders(db, contractor: str = None):
    if db is None:
        return []
    query = db.collection("purchase_orders")
    if contractor:
        query = query.where("contractor", "==", contractor)
    docs = query.stream()
    pos = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        pos.append(data)
    return pos

def create_purchase_order(db, po: schemas.PurchaseOrderCreate, project_id: str, username: str):
    if db is None:
        return None
    po_dict = po.model_dump()
    for k, v in po_dict.items():
        if isinstance(v, (date, datetime)):
            po_dict[k] = v.isoformat()
            
    po_dict["project_id"] = project_id
    po_dict["created_by"] = username
    po_dict["created_at"] = datetime.utcnow().isoformat()
    po_dict["updated_by"] = username
    po_dict["updated_at"] = datetime.utcnow().isoformat()
    
    doc_ref = db.collection("purchase_orders").document()
    doc_ref.set(po_dict)
    
    po_dict["id"] = doc_ref.id
    return po_dict

def update_purchase_order(db, po_id: str, po: schemas.PurchaseOrderUpdate, username: str):
    if db is None or not po_id:
        return None
    db_po = get_purchase_order(db, po_id)
    if not db_po:
        return None
        
    update_data = po.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if isinstance(v, (date, datetime)):
            update_data[k] = v.isoformat()
            
    for f in ["created_by", "created_at", "updated_by", "updated_at", "id", "project_id"]:
        update_data.pop(f, None)
        
    update_data["updated_by"] = username
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    db.collection("purchase_orders").document(po_id).update(update_data)
    return get_purchase_order(db, po_id)

def delete_purchase_order(db, po_id: str):
    if db is None or not po_id:
        return False
    db.collection("purchase_orders").document(po_id).delete()
    return True


# Dashboard statistics and alerts
def get_dashboard_stats(db, contractor: str = None):
    if db is None:
        return {"total_projects": 0, "projects_by_status": {}, "active_total_budget": 0.0}
        
    query = db.collection("projects")
    if contractor:
        query = query.where("contractor", "==", contractor)
        
    docs = query.stream()
    total_projects = 0
    status_counts = {
        "กำลังดำเนินการ": 0,
        "ล่าช้า": 0,
        "ส่งมอบแล้ว": 0
    }
    total_budget = 0.0
    
    for doc in docs:
        p = doc.to_dict()
        total_projects += 1
        status = p.get("status", "กำลังดำเนินการ")
        status_counts[status] = status_counts.get(status, 0) + 1
        
        try:
            total_budget += float(p.get("budget", 0.0))
        except (ValueError, TypeError):
            pass
                
    return {
        "total_projects": total_projects,
        "projects_by_status": status_counts,
        "active_total_budget": total_budget
    }

def get_dashboard_alerts(db, contractor: str = None):
    if db is None:
        return []
        
    today = date.today()
    target_date = today + timedelta(days=14)
    
    docs = db.collection("deliverables").where("status", "==", "รอดำเนินการ").stream()
    alerts = []
    
    for doc in docs:
        d = doc.to_dict()
        due_date_str = d.get("due_date")
        if not due_date_str:
            continue
            
        try:
            due_date = datetime.strptime(due_date_str.split("T")[0], "%Y-%m-%d").date()
        except ValueError:
            continue
            
        if due_date <= target_date:
            project_id = d.get("project_id")
            project = get_project(db, project_id)
            if not project:
                continue
                
            if contractor and project.get("contractor") != contractor:
                continue
                
            days_remaining = (due_date - today).days
            alerts.append({
                "deliverable_id": doc.id,
                "project_id": project_id,
                "project_name": project.get("name"),
                "deliverable_name": d.get("name"),
                "due_date": due_date.isoformat(),
                "days_remaining": days_remaining,
                "status": d.get("status")
            })
            
    alerts.sort(key=lambda x: x["days_remaining"])
    return alerts

def get_dashboard_po_alerts(db, contractor: str = None):
    if db is None:
        return []
        
    today = date.today()
    docs = db.collection("purchase_orders").where("delivery_status", "==", "ยังไม่ได้ส่ง").stream()
    alerts = []
    
    for doc in docs:
        po = doc.to_dict()
        if contractor and po.get("contractor") != contractor:
            continue
            
        due_date_str = po.get("due_date")
        if not due_date_str:
            continue
            
        try:
            due_date = datetime.strptime(due_date_str.split("T")[0], "%Y-%m-%d").date()
        except ValueError:
            continue
            
        days_remaining = (due_date - today).days
        if days_remaining <= 3:
            project_id = po.get("project_id")
            project = get_project(db, project_id)
            project_name = project.get("name") if project else "ไม่พบโครงการ"
            
            alerts.append({
                "po_id": doc.id,
                "project_id": project_id,
                "project_name": project_name,
                "po_number": po.get("po_number"),
                "budget": po.get("budget"),
                "due_date": due_date.isoformat(),
                "days_remaining": days_remaining,
                "delivery_status": po.get("delivery_status")
            })
            
    alerts.sort(key=lambda x: x["days_remaining"])
    return alerts

def log_user_action(db, username: str, action: str, target_type: str, target_name: str, details: str = None):
    if db is None:
        return None
        
    user = get_user_by_username(db, username)
    fullname = user.get("fullname") if user else None
    
    log_data = {
        "username": username,
        "fullname": fullname,
        "action": action,
        "target_type": target_type,
        "target_name": target_name,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details
    }
    
    doc_ref = db.collection("audit_logs").document()
    doc_ref.set(log_data)
    log_data["id"] = doc_ref.id
    return log_data
