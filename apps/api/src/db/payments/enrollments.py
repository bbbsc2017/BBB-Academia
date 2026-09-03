from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

from src.db.payments.config import PaymentProviderEnum


class EnrollmentStatusEnum(str, Enum):
    pending = "pending"
    active = "active"
    cancelled = "cancelled"
    failed = "failed"
    refunded = "refunded"


class PaymentsEnrollmentBase(SQLModel):
    status: EnrollmentStatusEnum = EnrollmentStatusEnum.pending
    provider: PaymentProviderEnum
    provider_specific_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class PaymentsEnrollment(PaymentsEnrollmentBase, table=True):
    __tablename__ = "paymentsenrollment"

    id: int | None = Field(default=None, primary_key=True)
    offer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("paymentsoffer.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
    update_date: str = ""


class PaymentsEnrollmentRead(PaymentsEnrollmentBase):
    id: int
    offer_id: int
    user_id: int
    org_id: int
    creation_date: str
    update_date: str
