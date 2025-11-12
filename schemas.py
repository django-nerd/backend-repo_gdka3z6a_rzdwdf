"""
Database Schemas

Define MongoDB collection schemas for the matchmaking platform.
Each Pydantic model represents a collection. Collection name is the lowercase
of the class name (e.g., Profile -> "profile").
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# Auth/session after successful payment
class Userauth(BaseModel):
    email: str = Field(..., description="User email used at checkout")
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer id")
    stripe_session_id: Optional[str] = Field(None, description="Stripe checkout session id")
    paid: bool = Field(False, description="Has completed payment")
    token: str = Field(..., description="Simple auth token issued after payment")
    verified: bool = Field(False, description="Admin verified badge")

# Core profile data
class Profile(BaseModel):
    userauth_id: str = Field(..., description="Reference to userauth _id as string")
    full_name: str
    gender: Literal['Pria','Wanita','Lainnya']
    birth_date: str  # ISO date string
    marital_status: Literal['Lajang','Duda/Janda']
    religion: Literal['Islam','Katolik','Protestan','Hindu','Budha','Khonghucu','Lainnya','Agnostik']
    islam_branch: Optional[Literal['Sunni','Syiah']] = None
    religion_level: Literal['Tidak menjalankan','Moderat','Strict']
    ethnicity: Optional[str] = None
    hobbies: Optional[List[str]] = []
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    wears_glasses: Optional[bool] = None
    address_origin: Optional[str] = None
    address_current: Optional[str] = None

    # Family
    siblings_count: Optional[int] = None
    family_condition: Optional[Literal['harmonis','tidak harmonis','orang tua bercerai','yatim','piatu']] = None

    # Health
    health_history: Optional[List[str]] = []
    health_notes: Optional[str] = None

    # Work & Education
    occupation: Optional[str] = None
    side_hustle: Optional[str] = None
    income_range: Optional[str] = None
    education_level: Optional[str] = None

    # Languages
    bahasa_indonesia: bool = True
    bahasa_inggris: bool = False
    bahasa_arab: bool = False
    bahasa_daerah: Optional[str] = None
    bahasa_lain: Optional[str] = None

    # Children Plan
    child_plan: Literal['Ingin punya anak','Tidak ingin punya anak','Sudah punya anak dan ingin tambah','Sudah punya anak dan tidak ingin tambah','Tidak yakin']

    # Love Language (multiple allowed)
    love_languages: List[str] = []

    # Lifestyle
    smoke: Optional[bool] = None
    alcohol: Optional[bool] = None
    diet: Optional[Literal['Vegetarian','Vegan','Pescatarian','Pemakan Segala']] = None
    physical_activity: Optional[Literal['Aktif','Sedang','Tidak aktif']] = None
    sleep_habit: Optional[Literal['Pagi hari','Malam hari','Tidak tentu']] = None
    time_management: Optional[Literal['Disiplin','Fleksibel','Santai']] = None
    shopping_habit: Optional[Literal['Hemat','Sesuai kebutuhan','Konsumtif']] = None

    # Social
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    linkedin: Optional[str] = None
    tiktok: Optional[str] = None

    city: Optional[str] = None
    country: Optional[str] = None
    photo_url: Optional[str] = None

# Likes between users
class Like(BaseModel):
    from_userauth_id: str
    to_userauth_id: str

# Match record (mutual like)
class Match(BaseModel):
    userauth_a: str
    userauth_b: str

# Chat message within a match
class Message(BaseModel):
    match_id: str
    from_userauth_id: str
    text: str

# Simple analytics snapshot (optional)
class Stat(BaseModel):
    total_users: int
    total_matches: int
    verified_users: int
    active_users_7d: int
