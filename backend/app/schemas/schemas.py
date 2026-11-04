from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Money = Annotated[Decimal, Field(ge=0, le=9999999, max_digits=9, decimal_places=2)]
Count = Annotated[int, Field(ge=0, le=100000)]
Positive = Annotated[int, Field(gt=0, le=100000)]
Specs = dict[Annotated[str, StringConstraints(min_length=1, max_length=80)], Annotated[str, StringConstraints(max_length=160)]]
Category = Literal["Ноутбук", "ПК", "Моноблок", "Міні-ПК", "Смартфон", "Планшет", "Смарт-годинник", "Консоль", "Монітор", "ДБЖ"]
Stage = Literal["registered", "diagnostics", "waiting_approval", "in_repair", "ready_for_pickup", "completed", "cancelled"]

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Login(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class Registration(Login):
    full_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(pattern=r"^\+?[0-9]{9,15}$")
    password: str = Field(min_length=8, max_length=128)

class StaffRegistration(Registration):
    role: Literal["client", "master", "admin"] = "client"
    specialization: str = Field(default="", max_length=180)

class UserEdit(Input):
    is_active: bool
    specialization: str = Field(default="", max_length=180)

class Hardware(Input):
    serial_number: str = Field(min_length=2, max_length=80)
    device_category: Category
    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    specifications: Specs = Field(default_factory=dict, max_length=40)
    cosmetic_condition: Long = ""
    @field_validator("serial_number")
    @classmethod
    def serial(cls, value):
        return value.upper()

class DeviceCreate(Hardware):
    owner_id: Positive
    save_preset: bool = False

class PresetCreate(Input):
    device_category: Category
    brand: str = Field(min_length=1, max_length=80)
    model_name: str = Field(min_length=1, max_length=120)
    default_specs: Specs = Field(default_factory=dict, max_length=40)
    typical_defects: Long = ""

class Upgrade(Input):
    field_name: str = Field(min_length=1, max_length=80)
    new_value: Text
    change_reason: Long = ""
    order_id: Positive | None = None

class Defect(Input):
    description: Long = Field(min_length=3)

class OrderCreate(Input):
    device_id: Positive | None = None
    new_device: Hardware | None = None
    master_id: Positive | None = None
    problem_description: Long = Field(min_length=3)
    completeness: Long = ""
    cosmetic_notes: Long = ""
    priority: Literal["normal", "urgent"] = "normal"
    is_warranty_case: bool = False

class OrderEdit(Input):
    diagnostics: Long | None = None
    internal_notes: Long | None = None
    master_id: Positive | None = None
    paid_amount: Money | None = None
    warranty_days: int | None = Field(default=None, ge=0, le=3650)

class Transition(Input):
    status: Stage
    comment: Long = ""

class Approval(Input):
    approved: bool
    expected_total: Money
    estimate_version: str = Field(min_length=1, max_length=64)
    comment: Long = ""

class WorkInput(Input):
    service_id: Positive | None = None
    work_name: Text | None = None
    price: Money | None = None
    updates_passport_spec: Specs = Field(default_factory=dict, max_length=10)

class OrderPartInput(Input):
    part_id: Positive
    quantity: Positive

class Quantity(Input):
    quantity: Positive

class PartInput(Input):
    sku: str = Field(min_length=1, max_length=60)
    name: Text
    category: str = Field(min_length=1, max_length=60)
    compatible_device_category: Category | Literal[""] = ""
    min_stock_level: Count = 0
    cost_price: Money
    sale_price: Money
    spec_upgrade_target: str = Field(default="", max_length=80)
    spec_upgrade_value: str = Field(default="", max_length=160)

class PartCreate(PartInput):
    quantity_in_stock: Count = 0

class ServiceInput(Input):
    code: str = Field(min_length=1, max_length=32)
    name: Text
    category: str = Field(min_length=1, max_length=60)
    default_price: Money
    estimated_hours: Money = 0
    warranty_days: int = Field(default=90, ge=0, le=3650)
