from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from app.core.config import settings
from app.core.security import hash_password
from app.db.database import Base,engine,SessionLocal
from app.db.models import User
from app.api import auth,instruments,tests,reports,dashboard,users,rules,attachments

app=FastAPI(title="NAWI Compliance & Test Report Automation System",version="0.1.0",description="SIH 2026 prototype. Evaluation rules require controlled configuration.")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(",")],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
for router in (auth.router,instruments.router,tests.router,tests.compliance_router,reports.router,dashboard.router,users.router,rules.router,attachments.router):app.include_router(router)
@app.on_event("startup")
def initialize():
    Base.metadata.create_all(bind=engine)
    # Keep existing local SQLite demos compatible as the prototype schema grows.
    if engine.dialect.name == "sqlite":
        additions={"users":{"is_active":"BOOLEAN NOT NULL DEFAULT 1"},"attachments":{"size_bytes":"INTEGER NOT NULL DEFAULT 0","uploaded_by":"INTEGER"},"compliance_results":{"rule_id":"INTEGER","evaluated_by":"INTEGER","calculated_unit":"VARCHAR(16) NOT NULL DEFAULT ''","limit_unit":"VARCHAR(16) NOT NULL DEFAULT ''"}}
        inspector=inspect(engine)
        with engine.begin() as conn:
            for table, columns in additions.items():
                present={c["name"] for c in inspector.get_columns(table)}
                for name, spec in columns.items():
                    if name not in present: conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")
    db=SessionLocal()
    try:
        for name,email,password,role in [("NAWI Administrator","admin@nawi.local","Admin@123","ADMIN"),("Laboratory Technician","technician@nawi.local","Tech@123","LAB_TECHNICIAN"),("Approving Officer","officer@nawi.local","Officer@123","APPROVING_OFFICER")]:
            if not db.query(User).filter_by(email=email).first():db.add(User(name=name,email=email,password_hash=hash_password(password),role=role))
        db.commit()
    finally:db.close()
@app.get("/api/health")
def health():return {"status":"ok","service":"nawi-compliance-api"}
