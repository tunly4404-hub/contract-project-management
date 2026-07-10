import os
import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import models
import crud
import schemas

# Drop and recreate database file to ensure clean V5 schema
if os.path.exists("projects.db"):
    try:
        os.remove("projects.db")
        print("Removed existing projects.db database file for clean V5 migration.")
    except Exception as e:
        print(f"Could not remove database file: {e}")

# Make sure tables exist
Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    try:
        # Clear existing data just in case
        db.query(models.User).delete()
        db.query(models.PurchaseOrder).delete()
        db.query(models.Document).delete()
        db.query(models.Deliverable).delete()
        db.query(models.Project).delete()
        db.commit()

        # Seed Users
        admin_user = schemas.UserCreate(
            username="admin",
            fullname="ผู้ดูแลระบบหลัก",
            role="admin",
            password="admin1234"
        )
        sittipan_user = schemas.UserCreate(
            username="sittipan",
            fullname="คุณ สิทธิพรรณ",
            role="user",
            password="sittipan123"
        )
        
        db_admin = crud.create_user(db, admin_user)
        db_sittipan = crud.create_user(db, sittipan_user)
        
        db_admin.role = "admin"
        db_admin.is_active = True
        db_sittipan.role = "user"
        db_sittipan.is_active = True
        db.commit()
        print("Seeded User profiles 'admin' and 'sittipan' successfully.")

        today = datetime.date.today()

        # Folders setup (V5 Audit subfolders check)
        os.makedirs("./uploads", exist_ok=True)
        os.makedirs("./uploads/pos", exist_ok=True)
        os.makedirs("./uploads/deliveries", exist_ok=True)

        # Create dummy documents
        with open("./uploads/mock_tor_erp.pdf", "w") as f:
            f.write("This is a mock TOR ERP document content.")
        with open("./uploads/mock_guarantee_receipt_erp.pdf", "w") as f:
            f.write("This is a mock contract guarantee receipt LG ERP content.")
        with open("./uploads/mock_guarantee_receipt_laptops.pdf", "w") as f:
            f.write("This is a mock contract guarantee receipt Cash Laptops content.")
        with open("./uploads/deliveries/mock_delivery_note.pdf", "w") as f:
            f.write("This is a mock delivery note document content.")

        # Project 1: ERP Software
        p1 = models.Project(
            name="โครงการพัฒนาซอฟต์แวร์ ERP องค์กร",
            owner="บริษัท เอไอ เอนเตอร์ไพรส์ จำกัด",
            budget=3500000.0,
            start_date=today - datetime.timedelta(days=40),
            end_date=today + datetime.timedelta(days=120),
            status="กำลังดำเนินการ",
            contract_number="CON-2026-0089",
            contractor="บริษัท มดงาน บุษยมาศ จำกัด",
            counterpart_status="ได้รับแล้ว",
            counterpart_date=today - datetime.timedelta(days=30),
            guarantee_amount=175000.0,
            guarantee_payment_type="หนังสือค้ำประกันธนาคาร (LG)",
            guarantee_receipt_status="ได้รับแล้ว",
            guarantee_receipt_date=today - datetime.timedelta(days=28),
            guarantee_receipt_path="/uploads/mock_guarantee_receipt_erp.pdf",
            guarantee_receipt_filename="Receipt_LG_ERP.pdf",
            work_order_date=today - datetime.timedelta(days=38),
            guarantee_bank="ธนาคารไทยพาณิชย์ (SCB)",
            guarantee_expiry_date=today + datetime.timedelta(days=365),
            job_type="งานจ้างพัฒนาซอฟต์แวร์",
            right_assignment="ไม่ได้โอนสิทธิ์",
            right_assignment_percentage=None,
            created_by="admin",
            updated_by="admin"
        )
        db.add(p1)
        db.flush()

        d1_1 = models.Deliverable(
            project_id=p1.id,
            name="งวดที่ 1: รายงานการวิเคราะห์ความต้องการและการออกแบบระบบ",
            due_date=today - datetime.timedelta(days=20),
            status="ส่งมอบแล้ว",
            delivery_no="DEL-ERP-001",
            created_by="admin",
            updated_by="admin"
        )
        d1_2 = models.Deliverable(
            project_id=p1.id,
            name="งวดที่ 2: ระบบบริหารจัดการคลังสินค้าและจัดซื้อ",
            due_date=today + datetime.timedelta(days=5),
            status="รอดำเนินการ",
            delivery_no=None,
            created_by="admin",
            updated_by="admin"
        )
        db.add_all([d1_1, d1_2])

        doc1 = models.Document(
            project_id=p1.id,
            filename="TOR_ERP_System.pdf",
            file_type="PDF",
            url_path="/uploads/mock_tor_erp.pdf"
        )
        db.add(doc1)

        # PO 1 for Project 1 (ERP) - 10 Days remaining (not in alert yet)
        po1 = models.PurchaseOrder(
            project_id=p1.id,
            po_number="PO-ERP-2026-0001",
            budget=500000.0,
            po_date=today - datetime.timedelta(days=20),
            delivery_duration_days=30,
            due_date=today + datetime.timedelta(days=10),
            owner="บริษัท เอไอ เอนเตอร์ไพรส์ จำกัด",
            contractor="บริษัท มดงาน บุษยมาศ จำกัด",
            material_type="โปรแกรมสำเร็จรูป",
            delivery_status="ยังไม่ได้ส่ง",
            created_by="admin",
            updated_by="admin"
        )
        db.add(po1)

        # Project 2: IT Security Network Upgrade
        p2 = models.Project(
            name="โครงการปรับปรุงเครือข่ายความปลอดภัยไอที",
            owner="กรมโยธาธิการและผังเมือง",
            budget=1200000.0,
            start_date=today - datetime.timedelta(days=15),
            end_date=today + datetime.timedelta(days=60),
            status="กำลังดำเนินการ",
            contract_number="CON-2026-0120",
            contractor="บริษัท ปาริภัทร จำกัด",
            counterpart_status="ได้รับแล้ว",
            counterpart_date=today - datetime.timedelta(days=12),
            guarantee_amount=60000.0,
            guarantee_payment_type="เงินสด / เงินโอน",
            guarantee_receipt_status="ยังไม่ได้รับ",
            guarantee_receipt_date=None,
            work_order_date=today - datetime.timedelta(days=12),
            guarantee_bank=None,
            guarantee_expiry_date=None,
            job_type="งานระบบเครือข่าย",
            right_assignment="โอนสิทธิ์",
            right_assignment_percentage=100.0,
            created_by="sittipan",
            updated_by="sittipan"
        )
        db.add(p2)
        db.flush()

        d2_1 = models.Deliverable(
            project_id=p2.id,
            name="การจัดหาอุปกรณ์ Firewall และ Switch",
            due_date=today + datetime.timedelta(days=10),
            status="รอดำเนินการ",
            internal_delivery_no="INT-NET-101",
            external_delivery_no="EXT-NET-901",
            created_by="sittipan",
            updated_by="sittipan"
        )
        db.add(d2_1)

        # PO 2 for Project 2 (Network) - Overdue (5 Days Ago) -> WILL alert!
        po2 = models.PurchaseOrder(
            project_id=p2.id,
            po_number="PO-NET-2026-088",
            budget=350000.0,
            po_date=today - datetime.timedelta(days=35),
            delivery_duration_days=30,
            due_date=today - datetime.timedelta(days=5),
            owner="กรมโยธาธิการและผังเมือง",
            contractor="บริษัท ปาริภัทร จำกัด",
            material_type="อุปกรณ์ไอที",
            delivery_status="ยังไม่ได้ส่ง",
            created_by="sittipan",
            updated_by="sittipan"
        )
        db.add(po2)

        # Project 3: Office Building and Landscape Renovation
        p3 = models.Project(
            name="โครงการปรับปรุงอาคารสำนักงานและภูมิทัศน์",
            owner="สำนักงานพัฒนาวิทยาศาสตร์และเทคโนโลยีแห่งชาติ (สวทช.)",
            budget=8500000.0,
            start_date=today - datetime.timedelta(days=180),
            end_date=today - datetime.timedelta(days=10),
            status="ล่าช้า",
            contract_number="CON-2026-0005",
            contractor="ห้างหุ้นส่วนจำกัด สิทธิพรรณ คอนแท๊ก",
            counterpart_status="ยังไม่ได้รับ",
            counterpart_date=None,
            guarantee_amount=425000.0,
            guarantee_payment_type="หนังสือค้ำประกันธนาคาร (LG)",
            guarantee_receipt_status="ยังไม่ได้รับ",
            guarantee_receipt_date=None,
            work_order_date=today - datetime.timedelta(days=175),
            guarantee_bank="ธนาคารกสิกรไทย (KBANK)",
            guarantee_expiry_date=today + datetime.timedelta(days=90),
            job_type="งานจ้างก่อสร้าง",
            right_assignment="โอนสิทธิ์",
            right_assignment_percentage=80.0,
            created_by="admin",
            updated_by="sittipan"
        )
        db.add(p3)
        db.flush()

        d3_1 = models.Deliverable(
            project_id=p3.id,
            name="งานปูพื้นกระเบื้องและทาสีภายในอาคาร",
            due_date=today - datetime.timedelta(days=5),
            status="รอดำเนินการ",
            internal_delivery_no="INT-BUILD-04",
            external_delivery_no="EXT-BUILD-04",
            created_by="admin",
            updated_by="sittipan"
        )
        db.add(d3_1)

        # PO 3 for Project 3 (Landscape) - Near due (2 Days remaining) -> WILL alert!
        po3 = models.PurchaseOrder(
            project_id=p3.id,
            po_number="PO-BUILD-2026-909",
            budget=120000.0,
            po_date=today - datetime.timedelta(days=28),
            delivery_duration_days=30,
            due_date=today + datetime.timedelta(days=2),
            owner="สำนักงานพัฒนาวิทยาศาสตร์และเทคโนโลยีแห่งชาติ (สวทช.)",
            contractor="ห้างหุ้นส่วนจำกัด สิทธิพรรณ คอนแท๊ก",
            material_type="วัสดุงานก่อสร้าง",
            delivery_status="ยังไม่ได้ส่ง",
            created_by="admin",
            updated_by="sittipan"
        )
        db.add(po3)

        # Project 4: Laptop Procurement
        p4 = models.Project(
            name="โครงการจัดซื้อคอมพิวเตอร์พกพาสำหรับบุคลากร",
            owner="มหาวิทยาลัยแห่งชาติ",
            budget=4500000.0,
            start_date=today - datetime.timedelta(days=90),
            end_date=today - datetime.timedelta(days=30),
            status="ส่งมอบแล้ว",
            contract_number="CON-2026-0044",
            contractor="บริษัท สบายตา ดีเวลลอปเม้นท์ จำกัด",
            counterpart_status="ได้รับแล้ว",
            counterpart_date=today - datetime.timedelta(days=80),
            guarantee_amount=225000.0,
            guarantee_payment_type="เงินสด / เงินโอน",
            guarantee_receipt_status="ได้รับแล้ว",
            guarantee_receipt_date=today - datetime.timedelta(days=78),
            guarantee_receipt_path="/uploads/mock_guarantee_receipt_laptops.pdf",
            guarantee_receipt_filename="Receipt_Cash_Laptops.pdf",
            work_order_date=today - datetime.timedelta(days=88),
            guarantee_bank=None,
            guarantee_expiry_date=None,
            job_type="งานจัดหาอุปกรณ์คอมพิวเตอร์",
            right_assignment="ไม่ได้โอนสิทธิ์",
            right_assignment_percentage=None,
            created_by="sittipan",
            updated_by="sittipan"
        )
        db.add(p4)
        db.flush()

        d4_1 = models.Deliverable(
            project_id=p4.id,
            name="จัดส่งเครื่องคอมพิวเตอร์พกพา 100 เครื่อง",
            due_date=today - datetime.timedelta(days=45),
            status="ส่งมอบแล้ว",
            delivery_no="DEL-LPT-99",
            created_by="sittipan",
            updated_by="sittipan"
        )
        db.add(d4_1)

        # PO 4 for Project 4 (Laptops) - Completed -> NOT in alert!
        po4 = models.PurchaseOrder(
            project_id=p4.id,
            po_number="PO-LPT-2026-003",
            budget=2000000.0,
            po_date=today - datetime.timedelta(days=60),
            delivery_duration_days=30,
            due_date=today - datetime.timedelta(days=30),
            owner="มหาวิทยาลัยแห่งชาติ",
            contractor="บริษัท สบายตา ดีเวลลอปเม้นท์ จำกัด",
            material_type="วัสดุสำนักงาน",
            delivery_no="DO-LPT-003",
            delivery_date=today - datetime.timedelta(days=32),
            delivery_status="ส่งมอบแล้ว",
            delivery_file_path="/uploads/deliveries/mock_delivery_note.pdf",
            delivery_file_filename="mock_delivery_note.pdf",
            created_by="sittipan",
            updated_by="sittipan"
        )
        db.add(po4)

        db.commit()
        print("Database V5 seeded successfully with mock projects, deliverables, documents, guarantees, POs, and Users.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
