"""Validated request and response schemas for authentication."""

from datetime import datetime, timezone
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)
    organization_name: str = Field(min_length=2, max_length=160)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name", "organization_name")
    @classmethod
    def trim_names(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be blank")
        return cleaned


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, min_length=6, max_length=8, pattern=r"^[0-9]{6,8}$")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class SetCredentialsRequest(BaseModel):
    """Lets an account without a password (WhatsApp or Google sign-in) add one, and an email if it has none."""

    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class AuthProvidersResponse(BaseModel):
    """Which social sign-in options this deployment has configured (so the UI only shows working buttons)."""

    google: bool
    whatsapp: bool


def normalize_phone_number(value: str) -> str:
    """Return an E.164 number ("+" and 8-15 digits, no leading zero), or raise ValueError."""
    cleaned = "".join(ch for ch in value.strip() if ch not in " -().")
    if not cleaned.startswith("+") or not cleaned[1:].isascii() or not cleaned[1:].isdigit():
        raise ValueError("Enter your WhatsApp number with the country code, for example +2348012345678")
    digits = cleaned[1:]
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        raise ValueError("Enter a valid WhatsApp number with the country code, for example +2348012345678")
    return f"+{digits}"


class WhatsAppCodeRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=32)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_phone_number(value)


class WhatsAppVerifyRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=32)
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    # Only used when this number has no account yet.
    full_name: str | None = Field(default=None, max_length=160)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_phone_number(value)

    @field_validator("full_name")
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # None for accounts created with WhatsApp (a phone number is the only identifier we have).
    email: EmailStr | None = None
    full_name: str
    is_active: bool
    # False when the account signs in with Google/WhatsApp and has no password of its own.
    has_password: bool = True
    email_verified_at: datetime | None = None
    created_at: datetime


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Workspace name must be at least 2 characters")
        return cleaned


class RenameOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Workspace name must be at least 2 characters")
        return cleaned


class UpdateAccountRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)

    @field_validator("full_name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned


class UpdateMemberRoleRequest(BaseModel):
    role: Literal["admin", "member"]


class MemberResponse(BaseModel):
    user_id: UUID
    email: EmailStr | None = None
    full_name: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    organization: OrganizationResponse


class CategoryResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    subcategories: list["CategoryResponse"] = []


class BusinessProfileRequest(BaseModel):
    """Full replacement of an organization's business profile (PUT semantics)."""

    business_name: str = Field(min_length=2, max_length=160)
    industry_id: UUID | None = None
    niche: str | None = Field(default=None, max_length=160)
    subcategory_id: UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    products_services: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=160)
    target_audience: str | None = Field(default=None, max_length=1000)
    audience_type: Literal["consumers", "businesses", "both"] | None = None
    geographic_market: str | None = Field(default=None, max_length=160)
    unique_selling_points: str | None = Field(default=None, max_length=1500)
    brand_voice: str | None = Field(default=None, max_length=500)
    preferred_tone: str | None = Field(default=None, max_length=120)
    preferred_words: str | None = Field(default=None, max_length=1000)
    avoided_words: str | None = Field(default=None, max_length=1000)
    brand_voice_mode: Literal["automatic", "manual", "hybrid"] = "hybrid"
    custom_ai_instructions: str | None = Field(default=None, max_length=2000)
    language: str = Field(default="en", min_length=2, max_length=35)
    marketing_goals: str | None = Field(default=None, max_length=1000)
    posting_frequency: str | None = Field(default=None, max_length=64)

    @field_validator(
        "business_name",
        "description",
        "niche",
        "products_services",
        "location",
        "target_audience",
        "geographic_market",
        "unique_selling_points",
        "brand_voice",
        "preferred_tone",
        "preferred_words",
        "avoided_words",
        "custom_ai_instructions",
        "language",
        "marketing_goals",
        "posting_frequency",
    )
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("business_name", "language")
    @classmethod
    def require_text(cls, value: str | None) -> str:
        if value is None or len(value) < 2:
            raise ValueError("This field must be at least 2 characters")
        return value


class BusinessProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: UUID
    business_name: str
    industry_id: UUID | None
    niche: str | None
    subcategory_id: UUID | None
    description: str | None
    products_services: str | None
    location: str | None
    target_audience: str | None
    audience_type: str | None
    geographic_market: str | None
    unique_selling_points: str | None
    brand_voice: str | None
    preferred_tone: str | None
    preferred_words: str | None
    avoided_words: str | None
    brand_voice_mode: str = "hybrid"
    custom_ai_instructions: str | None = None
    language: str
    marketing_goals: str | None
    posting_frequency: str | None
    profile_version: int = 1
    confirmed_at: datetime | None = None
    onboarding_completed_at: datetime | None = None
    updated_at: datetime


class BusinessContextResponse(BaseModel):
    organization_id: UUID
    business_name: str
    industry: str | None
    niche: str | None
    description: str | None
    location: str | None
    language: str
    products_services: str | None
    products: list[dict] = []
    target_audience: str | None
    audience_type: str | None
    geographic_market: str | None
    unique_selling_points: str | None
    marketing_goals: str | None
    brand_voice: str | None
    preferred_tone: str | None
    preferred_words: str | None
    avoided_words: str | None
    brand_voice_mode: str = "hybrid"
    custom_ai_instructions: str | None = None
    completeness_percent: int
    missing_fields: list[str]
    source: Literal["user_provided"] = "user_provided"


class GenerateCaptionRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    content_type: Literal["general", "promotion", "educational", "product"] = "general"

    @field_validator("topic")
    @classmethod
    def trim_topic(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Topic must be at least 2 characters")
        return cleaned


class GeneratedCaptionResponse(BaseModel):
    caption: str
    model: str


class GenerateVideoScriptRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    platform: Literal["tiktok", "instagram_reels", "facebook_reels", "youtube_shorts", "youtube_long"] = "tiktok"
    duration_seconds: int = Field(default=30, ge=15, le=600)
    call_to_action: str | None = Field(default=None, max_length=180)
    style: Literal["educational", "storytelling", "product_demo", "behind_the_scenes", "testimonial_style", "entertaining"] = "educational"

    @field_validator("topic")
    @classmethod
    def trim_script_topic(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Topic must be at least 2 characters")
        return cleaned


class GeneratedVideoScriptResponse(BaseModel):
    script: str
    model: str


class UsageItem(BaseModel):
    metric: str
    label: str
    limit: int | None  # null means unlimited
    used: int
    remaining: int | None


class UsageResponse(BaseModel):
    plan: str
    plan_name: str
    period_start: datetime
    metrics: list[UsageItem]


DraftStatus = Literal["draft", "approved", "rejected"]
ContentType = Literal["general", "promotion", "educational", "product", "video_script"]


class DraftCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    topic: str | None = Field(default=None, max_length=300)
    content_type: ContentType = "general"

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Content cannot be blank")
        return cleaned

    @field_validator("topic")
    @classmethod
    def trim_topic(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class DraftUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=12000)
    status: DraftStatus | None = None

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Content cannot be blank")
        return cleaned


class DraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    topic: str | None
    content_type: str
    status: str
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    entity_type: str
    entity_id: UUID | None
    summary: str
    actor_user_id: UUID | None
    actor_name: str
    created_at: datetime


class BusinessProductCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price_amount: int | None = Field(default=None, ge=0, le=10_000_000_000)
    price_currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_primary: bool = False

    @field_validator("name", "description", "price_currency")
    @classmethod
    def clean_product_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("name")
    @classmethod
    def require_product_name(cls, value: str | None) -> str:
        if value is None or len(value) < 2:
            raise ValueError("Product or service name must contain at least 2 characters")
        return value

    @field_validator("price_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class BusinessProductUpdateRequest(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def reject_null_name(cls, value):
        if isinstance(value, dict) and "name" in value and value["name"] is None:
            raise ValueError("Product or service name cannot be null")
        return value

    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price_amount: int | None = Field(default=None, ge=0, le=10_000_000_000)
    price_currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_primary: bool | None = None
    is_active: bool | None = None

    @field_validator("name", "description", "price_currency")
    @classmethod
    def clean_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("price_currency")
    @classmethod
    def normalize_update_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class BusinessProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    price_amount: int | None
    price_currency: str | None
    is_primary: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BusinessProfileConfirmationResponse(BaseModel):
    organization_id: UUID
    profile_version: int
    confirmed_at: datetime
    onboarding_completed_at: datetime
    message: str


class BusinessProfileVersionResponse(BaseModel):
    version_number: int
    action: str
    snapshot: dict
    changed_by_user_id: UUID | None
    created_at: datetime

class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"

    @field_validator("email")
    @classmethod
    def normalize_invitation_email(cls, value: str) -> str:
        return value.strip().lower()

class InvitationResponse(BaseModel):
    email: EmailStr
    role: str
    expires_at: datetime
    message: str

class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=200)


class InvitationAdminResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    expires_at: datetime
    accepted_at: datetime | None = None
    last_sent_at: datetime | None = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["pending", "accepted", "expired"]:
        if self.accepted_at is not None:
            return "accepted"
        expires = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return "expired" if expires <= datetime.now(timezone.utc) else "pending"

class TotpVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")
