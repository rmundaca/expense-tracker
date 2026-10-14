from typing import List, Optional

from pydantic import BaseModel


def to_dict(model: BaseModel, **kwargs) -> dict:
    """model.dict(); the NAS runs Pydantic v1 (see package/requirements.txt)."""
    return model.dict(**kwargs)


class OrmModel(BaseModel):
    class Config:
        orm_mode = True


# --- Accounts ---------------------------------------------------------------

class AccountCreate(BaseModel):
    name: str
    type: str
    currency: str = "CLP"
    balance: float = 0.0  # starting balance
    color: str = "#00c853"
    icon: str = "wallet"


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None
    balance: Optional[float] = None  # desired current balance -> creates an adjustment
    adjustment_note: Optional[str] = None


# --- Categories -------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str
    type: str  # expense, income
    color: str = "#78909c"
    icon: str = "tag"


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class CategoryOut(OrmModel):
    id: int
    name: str
    type: str
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool = True


# --- Transactions -----------------------------------------------------------

class TransactionCreate(BaseModel):
    type: str = "expense"  # expense, income, transfer
    amount: float
    currency: str = "CLP"
    exchange_rate: Optional[float] = None  # CLP per unit; resolved automatically when omitted
    date: str
    account_id: int
    destination_account_id: Optional[int] = None
    category_id: Optional[int] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []


class TransactionUpdate(BaseModel):
    type: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    date: Optional[str] = None
    account_id: Optional[int] = None
    destination_account_id: Optional[int] = None
    category_id: Optional[int] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # "confirmed" approves a pending movement
    tags: Optional[List[str]] = None


class TagOut(OrmModel):
    id: int
    name: str


class DuplicateRef(OrmModel):
    """The other movement of a likely double record (services/duplicates.py)."""
    id: int
    date: str
    merchant: Optional[str] = None
    amount: float
    currency: str
    source: Optional[str] = None
    status: str


class TransactionOut(OrmModel):
    id: int
    type: str
    amount: float
    currency: str
    exchange_rate: float
    rate_estimated: bool = False  # provisional: replaced by the official value after the next rates sync
    base_amount: Optional[float] = None
    date: str
    account_id: int
    destination_account_id: Optional[int] = None
    category_id: Optional[int] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    raw_text: Optional[str] = None
    source: Optional[str] = None
    status: str
    ai_confidence: Optional[float] = None
    ai_source: Optional[str] = None
    recurring_id: Optional[int] = None
    tags: List[TagOut] = []
    duplicate_of: Optional[DuplicateRef] = None  # only filled by the movement lists


# --- Recurring movements and budgets (POST and PUT take the whole object) -----

class RecurringIn(BaseModel):
    type: str = "expense"  # expense, income, transfer
    amount: float
    currency: str = "CLP"
    account_id: int
    destination_account_id: Optional[int] = None
    category_id: Optional[int] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    frequency: str = "month"  # day, week, month, year
    start_date: str
    end_date: Optional[str] = None
    auto_confirm: bool = True


class BudgetIn(BaseModel):
    name: str
    scope: str = "all"  # all, include, exclude
    category_ids: List[int] = []
    amount_type: str = "fixed"  # fixed, income_pct
    amount: float
    period: str = "month"  # day, week, month, year, once
    period_count: int = 1
    start_date: str
    end_date: Optional[str] = None  # required for "once"


class HomeCard(BaseModel):
    id: str
    visible: bool = True


# --- Rules ------------------------------------------------------------------

class RuleCreate(BaseModel):
    name: Optional[str] = None
    pattern: str
    match_field: str = "any"
    tx_type: str = "expense"
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    destination_account_id: Optional[int] = None
    is_regex: bool = False
    priority: int = 10
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    pattern: Optional[str] = None
    match_field: Optional[str] = None
    tx_type: Optional[str] = None
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    destination_account_id: Optional[int] = None
    is_regex: Optional[bool] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class RuleOut(OrmModel):
    id: int
    name: Optional[str] = None
    pattern: str
    match_field: Optional[str] = None
    tx_type: Optional[str] = None
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    destination_account_id: Optional[int] = None
    is_regex: bool = False
    priority: int = 10
    is_active: bool = True


# --- Banks ------------------------------------------------------------------

class BankUpdate(BaseModel):
    bank_name: Optional[str] = None
    sender_emails: Optional[List[str]] = None
    default_account_id: Optional[int] = None
    is_enabled: Optional[bool] = None


# --- Mail / system ------------------------------------------------------------

class MailSettingsUpdate(BaseModel):
    sync_enabled: Optional[bool] = None
    interval_mins: Optional[int] = None
    lookback_days: Optional[int] = None


class MailAccountIn(BaseModel):
    """Create (provider, name and email required) or update a mailbox. host/port/security only apply to
    imap and pop3; password: empty = keep the stored one."""
    name: Optional[str] = None
    provider: Optional[str] = None
    email: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    security: Optional[str] = None
    folders: Optional[List[str]] = None
    password: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_tenant: Optional[str] = None
    is_enabled: Optional[bool] = None


class MailTestRequest(MailAccountIn):
    account_id: Optional[int] = None  # stored mailbox the form edits: its password is used when none is typed


class CsvImportRequest(BaseModel):
    csv_content: str


class ResetDataRequest(BaseModel):
    confirm: str


class LanguageRequest(BaseModel):
    language: str  # en, es (app/i18n)


# --- Auth -------------------------------------------------------------------

class AuthSetupRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# --- Users (administrators only) ---------------------------------------------

class UserCreate(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    is_admin: bool = False


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    password: Optional[str] = None  # resets the password and closes that user's sessions
