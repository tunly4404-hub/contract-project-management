from pydantic import BaseModel
from datetime import date, datetime
from typing import List, Optional, Dict

# User Authentication Schemas (V5)
class UserBase(BaseModel):
    username: str
    fullname: str
    role: Optional[str] = "user"
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True

class UserResetPassword(BaseModel):
    new_password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


# Deliverable Schemas
class DeliverableBase(BaseModel):
    name: str
    due_date: date
    status: str = "รอดำเนินการ"
    
    # V3 fields
    delivery_no: Optional[str] = None
    internal_delivery_no: Optional[str] = None
    external_delivery_no: Optional[str] = None

    # V5 Audit fields
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

class DeliverableCreate(DeliverableBase):
    pass

class DeliverableUpdate(BaseModel):
    name: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    
    # V3 fields
    delivery_no: Optional[str] = None
    internal_delivery_no: Optional[str] = None
    external_delivery_no: Optional[str] = None

class Deliverable(DeliverableBase):
    id: int
    project_id: int

    class Config:
        from_attributes = True


# Document Schemas
class DocumentBase(BaseModel):
    filename: str
    file_type: str
    url_path: str

class Document(DocumentBase):
    id: int
    project_id: int

    class Config:
        from_attributes = True


# Purchase Order Schemas (V4)
class PurchaseOrderBase(BaseModel):
    po_number: str
    budget: float
    po_date: date
    delivery_duration_days: int
    due_date: date
    owner: str
    contractor: str
    material_type: str
    
    po_file_path: Optional[str] = None
    po_file_filename: Optional[str] = None
    quotation_file_path: Optional[str] = None
    quotation_file_filename: Optional[str] = None
    
    delivery_no: Optional[str] = None
    delivery_date: Optional[date] = None
    delivery_status: str = "ยังไม่ได้ส่ง"
    delivery_file_path: Optional[str] = None
    delivery_file_filename: Optional[str] = None

    # V5 Audit fields
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

class PurchaseOrderCreate(PurchaseOrderBase):
    pass

class PurchaseOrderUpdate(BaseModel):
    po_number: Optional[str] = None
    budget: Optional[float] = None
    po_date: Optional[date] = None
    delivery_duration_days: Optional[int] = None
    due_date: Optional[date] = None
    owner: Optional[str] = None
    contractor: Optional[str] = None
    material_type: Optional[str] = None
    
    po_file_path: Optional[str] = None
    po_file_filename: Optional[str] = None
    quotation_file_path: Optional[str] = None
    quotation_file_filename: Optional[str] = None
    
    delivery_no: Optional[str] = None
    delivery_date: Optional[date] = None
    delivery_status: Optional[str] = None
    delivery_file_path: Optional[str] = None
    delivery_file_filename: Optional[str] = None

class PurchaseOrder(PurchaseOrderBase):
    id: int
    project_id: int

    class Config:
        from_attributes = True


# Project Schemas
class ProjectBase(BaseModel):
    name: str
    owner: str
    budget: float
    start_date: date
    end_date: date
    status: str = "กำลังดำเนินการ"
    
    # V2 fields
    contract_number: Optional[str] = None
    contractor: Optional[str] = None
    counterpart_status: str = "ยังไม่ได้รับ"
    counterpart_date: Optional[date] = None
    guarantee_amount: float = 0.0
    guarantee_payment_type: str = "หนังสือค้ำประกันธนาคาร (LG)"
    guarantee_receipt_status: str = "ยังไม่ได้รับ"
    guarantee_receipt_date: Optional[date] = None
    guarantee_receipt_path: Optional[str] = None
    guarantee_receipt_filename: Optional[str] = None
    
    # V3 fields
    work_order_date: Optional[date] = None
    guarantee_bank: Optional[str] = None
    guarantee_expiry_date: Optional[date] = None
    job_type: Optional[str] = None
    right_assignment: str = "ไม่ได้โอนสิทธิ์" # ไม่ได้โอนสิทธิ์, โอนสิทธิ์
    right_assignment_percentage: Optional[float] = None

    # V5 Audit fields
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    owner: Optional[str] = None
    budget: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    
    # V2 fields
    contract_number: Optional[str] = None
    contractor: Optional[str] = None
    counterpart_status: Optional[str] = None
    counterpart_date: Optional[date] = None
    guarantee_amount: Optional[float] = None
    guarantee_payment_type: Optional[str] = None
    guarantee_receipt_status: Optional[str] = None
    guarantee_receipt_date: Optional[date] = None
    guarantee_receipt_path: Optional[str] = None
    guarantee_receipt_filename: Optional[str] = None
    
    # V3 fields
    work_order_date: Optional[date] = None
    guarantee_bank: Optional[str] = None
    guarantee_expiry_date: Optional[date] = None
    job_type: Optional[str] = None
    right_assignment: Optional[str] = None
    right_assignment_percentage: Optional[float] = None

class Project(ProjectBase):
    id: int
    deliverables: List[Deliverable] = []
    documents: List[Document] = []
    purchase_orders: List[PurchaseOrder] = []

    class Config:
        from_attributes = True


# Dashboard Schemas
class DashboardStats(BaseModel):
    total_projects: int
    projects_by_status: Dict[str, int]
    active_total_budget: float

class DashboardAlert(BaseModel):
    deliverable_id: int
    project_id: int
    project_name: str
    deliverable_name: str
    due_date: date
    days_remaining: int
    status: str

# V4 Dashboard Alert Schema for PO Deliveries
class DashboardPOAlert(BaseModel):
    po_id: int
    project_id: int
    project_name: str
    po_number: str
    budget: float
    due_date: date
    days_remaining: int
    delivery_status: str


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: str
    fullname: Optional[str] = None
    action: str
    target_type: str
    target_name: Optional[str] = None
    timestamp: datetime
    details: Optional[str] = None

    class Config:
        from_attributes = True
