import re
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Money = Annotated[Decimal, Field(ge=0, le=9999999, max_digits=9, decimal_places=2)]
Count = Annotated[int, Field(ge=0, le=100000)]
Positive = Annotated[int, Field(gt=0, le=100000)]
Specs = dict[Annotated[str, StringConstraints(min_length=1, max_length=80)], Annotated[str, StringConstraints(max_length=160)]]
Category = Literal["Ноутбук", "ПК", "Моноблок", "Міні-ПК", "Смартфон", "Планшет", "Смарт-годинник", "Консоль", "Монітор", "ДБЖ"]
Stage = Literal["registered", "diagnostics", "waiting_approval", "in_repair", "ready_for_pickup", "completed", "cancelled", "returned"]

def normalize_phone(value):
    """Приводить 050 123-45-67, 0501234567 і 380501234567 до єдиного вигляду +380501234567."""
    if not isinstance(value, str):
        return value
    digits = re.sub(r"[\s\-().]", "", value)
    if re.fullmatch(r"0\d{9}", digits):
        return "+38" + digits
    if re.fullmatch(r"380\d{9}", digits):
        return "+" + digits
    return digits

Phone = Annotated[str, BeforeValidator(normalize_phone), StringConstraints(pattern=r"^\+?[0-9]{9,15}$")]

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Login(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class GoogleLogin(Input):
    credential: str = Field(min_length=20, max_length=4096)
    phone: Phone | None = None

class Registration(Login):
    full_name: str = Field(min_length=1, max_length=150)
    phone: Phone
    password: str = Field(min_length=8, max_length=128)

class StaffRegistration(Registration):
    role: Literal["client", "master", "admin"] = "client"
    specialization: str = Field(default="", max_length=180)

class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

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

class NewDevice(Input):
    """Пристрій, який вводить клієнт або приймальник: серійний номер і характеристики необов'язкові."""
    serial_number: str | None = Field(default=None, max_length=80)
    device_category: Category
    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    specifications: Specs = Field(default_factory=dict, max_length=40)
    cosmetic_condition: Long = ""
    @field_validator("serial_number")
    @classmethod
    def serial(cls, value):
        value = (value or "").strip().upper()
        if value and len(value) < 2:
            raise ValueError("Серійний номер занадто короткий")
        return value or None

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

class OwnerTransfer(Input):
    """Пристрій продали або подарували: паспорт переходить до іншого клієнта."""
    owner_id: Positive
    reason: Long = ""

class Defect(Input):
    description: Long = Field(min_length=3)

class Delivery(Input):
    """Самовивіз або відправка у відділення чи поштомат Нової Пошти."""
    method: Literal["pickup", "nova_poshta"] = "pickup"
    city: str = Field(default="", max_length=80)
    branch: str = Field(default="", max_length=120)
    @model_validator(mode="after")
    def address_for_shipping(self):
        if self.method == "nova_poshta" and (len(self.city) < 2 or not self.branch):
            raise ValueError("Для відправки Новою Поштою вкажіть місто та відділення.")
        if self.method == "pickup":
            self.city, self.branch = "", ""
        return self

class Shipment(Input):
    ttn: str = Field(pattern=r"^\d{14}$", description="Номер експрес-накладної Нової Пошти, 14 цифр")
    @field_validator("ttn", mode="before")
    @classmethod
    def digits_only(cls, value):
        return re.sub(r"\s", "", value) if isinstance(value, str) else value

class TelegramNotifications(Input):
    enabled: bool

class RatingInput(Input):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)

class OrderCreate(Input):
    device_id: Positive | None = None
    new_device: NewDevice | None = None
    master_id: Positive | None = None
    problem_description: Long = Field(min_length=3)
    completeness: Long = ""
    cosmetic_notes: Long = ""
    priority: Literal["normal", "urgent"] = "normal"
    is_warranty_case: bool = False
    warranty_claim: bool = False  # клієнт просить гарантійний ремонт; рішення за працівником
    delivery: Delivery | None = None

class OrderEdit(Input):
    diagnostics: Long | None = None
    internal_notes: Long | None = None
    master_id: Positive | None = None
    paid_amount: Money | None = None
    warranty_days: int | None = Field(default=None, ge=0, le=3650)
    is_warranty_case: bool | None = None

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

class QuickRequest(Input):
    full_name: str = Field(min_length=2, max_length=150)
    phone: Phone
    device: NewDevice
    problem_description: Long = Field(min_length=3)
    delivery: Delivery | None = None
    website: str = Field(default="", max_length=200)  # приманка для ботів: людина це поле не бачить

class Intake(Input):
    phone: Phone | None = None
    full_name: str | None = Field(default=None, max_length=150)
    device_id: Positive | None = None
    device: NewDevice | None = None
    problem_description: Long = Field(min_length=3)
    completeness: Long = ""
    cosmetic_notes: Long = ""
    priority: Literal["normal", "urgent"] = "normal"
    master_id: Positive | None = None
    is_warranty_case: bool = False
    delivery: Delivery | None = None
    save_preset: bool = False
    @model_validator(mode="after")
    def source(self):
        if bool(self.device_id) == bool(self.device):
            raise ValueError("Оберіть наявний пристрій або внесіть дані нового")
        if self.device and not self.phone:
            raise ValueError("Вкажіть телефон клієнта")
        return self

class Claim(Input):
    token: str = Field(min_length=10, max_length=200)

class CompleteRegistration(Input):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class SerialInput(Input):
    serial_number: str = Field(min_length=2, max_length=80)
    @field_validator("serial_number")
    @classmethod
    def serial(cls, value):
        return value.upper()

class PaymentInput(Input):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: Literal["cash", "card", "transfer"]
    note: str = Field(default="", max_length=200)

class ClientCancel(Input):
    comment: str = Field(default="", max_length=1000)

class ReadNotifications(Input):
    ids: list[Positive] = Field(default_factory=list, max_length=200)
