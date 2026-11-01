"""Schemas for Telegram notification recipients and test results."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, field_validator


class TrustedContactInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    chat_id: str = Field(min_length=5, max_length=20, pattern=r"^-?\d{5,20}$")
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Name cannot be blank.")
        return name

    @field_validator("chat_id", mode="before")
    @classmethod
    def normalize_chat_id(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class TrustedContactResponse(BaseModel):
    id: int
    name: str
    chat_id: str
    enabled: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class TrustedContactListResponse(BaseModel):
    contacts: List[TrustedContactResponse]


class ContactNotificationTestResult(BaseModel):
    contact_id: int
    name: str
    success: bool
    message: str


class ContactNotificationTestBatch(BaseModel):
    total: int
    success_count: int
    failure_count: int
    results: List[ContactNotificationTestResult]
