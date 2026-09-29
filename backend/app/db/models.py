from datetime import datetime, date
from sqlalchemy import String, Float, Integer, DateTime, Date, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[int] = mapped_column(primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    serial_number: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    instrument_type: Mapped[str] = mapped_column(String(160))
    accuracy_class: Mapped[str] = mapped_column(String(8))
    capacity_unit: Mapped[str] = mapped_column(String(8))
    max_capacity: Mapped[float] = mapped_column(Float)
    min_capacity: Mapped[float] = mapped_column(Float)
    verification_interval_e: Mapped[float] = mapped_column(Float)
    display_interval_d: Mapped[float] = mapped_column(Float)
    number_of_verification_intervals_n: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sessions: Mapped[list["TestSession"]] = relationship(back_populates="instrument")

class TestSession(Base):
    __tablename__ = "test_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    test_date: Mapped[date] = mapped_column(Date, default=date.today)
    laboratory: Mapped[str] = mapped_column(String(180), default="")
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    instrument: Mapped[Instrument] = relationship(back_populates="sessions")
    operator: Mapped[User] = relationship()
    observations: Mapped[list["TestObservation"]] = relationship(cascade="all, delete-orphan")
    results: Mapped[list["ComplianceResult"]] = relationship(cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="test_session",cascade="all, delete-orphan")

class TestObservation(Base):
    __tablename__ = "test_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    test_session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"))
    test_type: Mapped[str] = mapped_column(String(32))
    test_point: Mapped[str] = mapped_column(String(100), default="")
    applied_load: Mapped[float] = mapped_column(Float)
    indicated_value: Mapped[float] = mapped_column(Float)
    error: Mapped[float] = mapped_column(Float, default=0)
    observation_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ComplianceResult(Base):
    __tablename__ = "compliance_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    test_session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"))
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("rule_configurations.id"), nullable=True)
    evaluated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    test_type: Mapped[str] = mapped_column(String(32))
    limit_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    calculated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    calculated_unit: Mapped[str] = mapped_column(String(16), default="")
    limit_unit: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(24))
    details: Mapped[str] = mapped_column(Text)
    standard_name: Mapped[str] = mapped_column(String(80), default="OIML R-76")
    standard_version: Mapped[str] = mapped_column(String(40), default="UNCONFIGURED")
    rule_code: Mapped[str] = mapped_column(String(80), default="")
    rule_description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    test_session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"))
    report_number: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    pdf_path: Mapped[str] = mapped_column(String(500), default="")
    docx_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    test_session: Mapped["TestSession"] = relationship(back_populates="reports")

class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"), nullable=True)
    test_session_id: Mapped[int | None] = mapped_column(ForeignKey("test_sessions.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    test_session: Mapped["TestSession | None"] = relationship()

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    details: Mapped[str] = mapped_column(Text, default="")

class RuleConfiguration(Base):
    __tablename__ = "rule_configurations"
    id: Mapped[int] = mapped_column(primary_key=True)
    standard_name: Mapped[str] = mapped_column(String(100))
    standard_version: Mapped[str] = mapped_column(String(80))
    rule_code: Mapped[str] = mapped_column(String(100), index=True)
    test_type: Mapped[str] = mapped_column(String(32), index=True)
    accuracy_class: Mapped[str] = mapped_column(String(8), index=True)
    applicable_range: Mapped[dict] = mapped_column(JSON, default=dict)
    limit_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    comparison_operator: Mapped[str] = mapped_column(String(8))
    description: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
