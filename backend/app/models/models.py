from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import false, BigInteger, Boolean, SmallInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base

def now():
    return datetime.now(timezone.utc)

def timestamp():
    return mapped_column(DateTime(timezone=True), default=now)

def money():
    return mapped_column(Numeric(12, 2), default=Decimal("0"))

def json_column():
    return mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=dict)

class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('client','master','admin')", name="valid_role"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    phone: Mapped[str] = mapped_column(String(24), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default="client")
    specialization: Mapped[str] = mapped_column(String(180), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    telegram_link_code: Mapped[str | None] = mapped_column(String(32), unique=True)
    # чат лишається прив'язаним, але сповіщення призупинено командою /stop
    telegram_muted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    telegram_link_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # зміна пароля збільшує версію, і всі раніше видані токени входу стають недійсними
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = timestamp()

class ModelPreset(Base):
    __tablename__ = "device_model_presets"
    __table_args__ = (UniqueConstraint("device_category", "brand", "model_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    device_category: Mapped[str] = mapped_column(String(40))
    brand: Mapped[str] = mapped_column(String(80))
    model_name: Mapped[str] = mapped_column(String(120))
    default_specs: Mapped[dict] = json_column()
    typical_defects: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = timestamp()

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    serial_number: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_category: Mapped[str] = mapped_column(String(40))
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    specifications: Mapped[dict] = json_column()
    cosmetic_condition: Mapped[str] = mapped_column(Text, default="")
    known_defects_history: Mapped[list] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=list)
    created_at: Mapped[datetime] = timestamp()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class Order(Base):
    __tablename__ = "repair_orders"
    __table_args__ = (
        CheckConstraint("status IN ('registered','diagnostics','waiting_approval','in_repair','ready_for_pickup','completed','cancelled')", name="valid_status"),
        CheckConstraint("client_approval_status IN ('pending','approved','rejected')", name="valid_approval"),
        CheckConstraint("warranty_days >= 0 AND paid_amount >= 0", name="valid_order_amounts"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="valid_rating"),
        CheckConstraint("delivery_method IN ('pickup', 'nova_poshta')", name="valid_delivery"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    master_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="registered", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    problem_description: Mapped[str] = mapped_column(Text)
    completeness: Mapped[str] = mapped_column(Text, default="")
    cosmetic_notes: Mapped[str] = mapped_column(Text, default="")
    diagnostics: Mapped[str] = mapped_column(Text, default="")
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    is_warranty_case: Mapped[bool] = mapped_column(default=False)
    works_total: Mapped[Decimal] = money()
    parts_total: Mapped[Decimal] = money()
    total_cost: Mapped[Decimal] = money()
    paid_amount: Mapped[Decimal] = money()
    approved_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    client_approval_status: Mapped[str] = mapped_column(String(15), default="pending")
    approval_comment: Mapped[str] = mapped_column(Text, default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warranty_days: Mapped[int] = mapped_column(default=90)
    warranty_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # оцінка клієнта після завершення ремонту
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    rating_comment: Mapped[str] = mapped_column(Text, default="", server_default="")
    rated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # коли бот нагадав про кінець гарантії та про профілактику (щоб не надсилати двічі)
    warranty_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    maintenance_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # спосіб повернення пристрою: самовивіз або відправка Новою Поштою
    delivery_method: Mapped[str] = mapped_column(String(15), default="pickup", server_default="pickup")
    delivery_city: Mapped[str] = mapped_column(String(80), default="", server_default="")
    delivery_branch: Mapped[str] = mapped_column(String(120), default="", server_default="")
    delivery_ttn: Mapped[str | None] = mapped_column(String(14))
    created_at: Mapped[datetime] = timestamp()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class SpecHistory(Base):
    __tablename__ = "device_spec_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("repair_orders.id"))
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    field_name: Mapped[str] = mapped_column(String(80))
    old_value: Mapped[str] = mapped_column(Text)
    new_value: Mapped[str] = mapped_column(Text)
    change_reason: Mapped[str] = mapped_column(Text)
    changed_at: Mapped[datetime] = timestamp()

class StatusHistory(Base):
    __tablename__ = "order_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("repair_orders.id"), index=True)
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    old_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str] = mapped_column(Text, default="")
    changed_at: Mapped[datetime] = timestamp()

class Service(Base):
    __tablename__ = "service_catalog"
    __table_args__ = (CheckConstraint("default_price >= 0 AND estimated_hours >= 0 AND warranty_days >= 0", name="valid_service"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(60))
    default_price: Mapped[Decimal] = money()
    estimated_hours: Mapped[Decimal] = money()
    warranty_days: Mapped[int] = mapped_column(default=90)

class Work(Base):
    __tablename__ = "order_works"
    __table_args__ = (CheckConstraint("price >= 0", name="nonnegative_work_price"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("repair_orders.id"), index=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("service_catalog.id"))
    work_name: Mapped[str] = mapped_column(String(160))
    master_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    price: Mapped[Decimal] = money()
    updates_passport_spec: Mapped[dict] = json_column()
    created_at: Mapped[datetime] = timestamp()

class Part(Base):
    __tablename__ = "spare_parts"
    __table_args__ = (CheckConstraint("quantity_in_stock >= 0 AND min_stock_level >= 0 AND cost_price >= 0 AND sale_price >= 0", name="valid_inventory"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(60))
    compatible_device_category: Mapped[str] = mapped_column(String(40), default="")
    quantity_in_stock: Mapped[int] = mapped_column(default=0)
    min_stock_level: Mapped[int] = mapped_column(default=0)
    cost_price: Mapped[Decimal] = money()
    sale_price: Mapped[Decimal] = money()
    spec_upgrade_target: Mapped[str] = mapped_column(String(80), default="")
    spec_upgrade_value: Mapped[str] = mapped_column(String(160), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class OrderPart(Base):
    __tablename__ = "order_parts"
    __table_args__ = (CheckConstraint("quantity > 0 AND unit_cost_price >= 0 AND unit_sale_price >= 0", name="valid_order_part"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("repair_orders.id"), index=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("spare_parts.id"))
    part_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int]
    unit_cost_price: Mapped[Decimal] = money()
    unit_sale_price: Mapped[Decimal] = money()
    total_sale_price: Mapped[Decimal] = money()
    spec_upgrade_target: Mapped[str] = mapped_column(String(80), default="")
    spec_upgrade_value: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = timestamp()

class Movement(Base):
    __tablename__ = "inventory_transactions"
    __table_args__ = (CheckConstraint("stock_after >= 0 AND change_amount != 0", name="valid_movement"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("spare_parts.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("repair_orders.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    change_amount: Mapped[int]
    stock_after: Mapped[int]
    reason: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = timestamp()

class DevicePhoto(Base):
    __tablename__ = "device_photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("repair_orders.id"), index=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    caption: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = timestamp()

class Payment(Base):
    """Окрема оплата за заявкою: можна прийняти частину готівкою, а решту карткою."""
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="positive_payment"),
                      CheckConstraint("method IN ('cash', 'card', 'transfer')", name="valid_payment_method"))
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("repair_orders.id"), index=True)
    amount: Mapped[Decimal] = money()
    method: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(String(200), default="")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = timestamp()

class Notification(Base):
    """Сповіщення працівника на сайті (дзвіночок у верхньому рядку)."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("repair_orders.id"))
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = timestamp()
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
