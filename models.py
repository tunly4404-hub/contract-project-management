from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    fullname = Column(String, nullable=False)
    role = Column(String, nullable=True, default="user")
    is_active = Column(Boolean, default=True, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    budget = Column(Float, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    contract_signing_date = Column(Date, nullable=True)
    status = Column(String, nullable=False, default="กำลังดำเนินการ") # กำลังดำเนินการ, ล่าช้า, ส่งมอบแล้ว

    # V2 Fields
    contract_number = Column(String, nullable=True)
    contractor = Column(String, nullable=True)
    counterpart_status = Column(String, nullable=False, default="ยังไม่ได้รับ") # ยังไม่ได้รับ, ได้รับแล้ว
    counterpart_date = Column(Date, nullable=True)
    guarantee_amount = Column(Float, nullable=False, default=0.0)
    guarantee_payment_type = Column(String, nullable=False, default="หนังสือค้ำประกันธนาคาร (LG)") # หนังสือค้ำประกันธนาคาร (LG), เงินสด / เงินโอน
    guarantee_receipt_status = Column(String, nullable=False, default="ยังไม่ได้รับ") # ยังไม่ได้รับ, ได้รับแล้ว
    guarantee_receipt_date = Column(Date, nullable=True)
    guarantee_receipt_path = Column(String, nullable=True)
    guarantee_receipt_filename = Column(String, nullable=True)
    guarantee_receipt_number = Column(String, nullable=True)
    guarantee_document_path = Column(String, nullable=True)
    guarantee_document_filename = Column(String, nullable=True)

    # V3 Fields
    work_order_date = Column(Date, nullable=True)
    guarantee_bank = Column(String, nullable=True)
    guarantee_expiry_date = Column(Date, nullable=True)
    job_type = Column(String, nullable=True)
    right_assignment = Column(String, nullable=False, default="ไม่ได้โอนสิทธิ์") # ไม่ได้โอนสิทธิ์, โอนสิทธิ์
    right_assignment_percentage = Column(Float, nullable=True)

    # V5 Audit Trail Fields
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deliverables = relationship("Deliverable", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="project", cascade="all, delete-orphan")


class Deliverable(Base):
    __tablename__ = "deliverables"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False) # รายการวัสดุ/งวดงาน
    due_date = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="รอดำเนินการ") # รอดำเนินการ, ส่งมอบแล้ว

    # V3 Fields
    delivery_no = Column(String, nullable=True)
    internal_delivery_no = Column(String, nullable=True)
    external_delivery_no = Column(String, nullable=True)

    # V5 Audit Trail Fields
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="deliverables")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    url_path = Column(String, nullable=False)

    project = relationship("Project", back_populates="documents")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    po_number = Column(String, nullable=False)
    budget = Column(Float, nullable=False)
    po_date = Column(Date, nullable=False)
    delivery_duration_days = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    owner = Column(String, nullable=False)
    contractor = Column(String, nullable=False)
    material_type = Column(String, nullable=False)
    
    # PO attachments
    po_file_path = Column(String, nullable=True)
    po_file_filename = Column(String, nullable=True)
    quotation_file_path = Column(String, nullable=True)
    quotation_file_filename = Column(String, nullable=True)
    
    # Delivery tracking fields
    delivery_no = Column(String, nullable=True)
    delivery_date = Column(Date, nullable=True)
    delivery_status = Column(String, nullable=False, default="ยังไม่ได้ส่ง") # ยังไม่ได้ส่ง, ส่งมอบแล้ว
    delivery_file_path = Column(String, nullable=True)
    delivery_file_filename = Column(String, nullable=True)

    # V5 Audit Trail Fields
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="purchase_orders")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String, nullable=False, index=True)
    fullname = Column(String, nullable=True)
    action = Column(String, nullable=False) # e.g. "สร้าง", "แก้ไข", "ลบ"
    target_type = Column(String, nullable=False) # e.g. "โครงการ", "ใบสั่งซื้อ PO", "ใบส่งมอบของ"
    target_name = Column(String, nullable=True) # e.g. "โครงการหลัก", "PO-1029"
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    details = Column(String, nullable=True)
