from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy import JSON, Column, ForeignKey, Integer, Boolean
from sqlmodel import Field, SQLModel


# Matches the existing Postgres type `paymentproviderenum`, created by
# migrations/versions/0314ec7791e1_payments.py with only 'STRIPE'. BOLD and
# OPENPAY are added to that same type by this feature's migration via
# `ALTER TYPE paymentproviderenum ADD VALUE`.
class PaymentProviderEnum(str, Enum):
    STRIPE = "STRIPE"
    BOLD = "BOLD"
    OPENPAY = "OPENPAY"


# Matches the existing Postgres type `paymentsmodeenum` (see
# migrations/versions/c1d2e3f4a5b6_rename_paymentsmode_enum.py for why the
# name is `paymentsmodeenum`, not `paymentsmodenum`). Only meaningful for
# Stripe (standard vs Express Connect) — Bold/OpenPay always use 'standard'.
class PaymentsModeEnum(str, Enum):
    standard = "standard"
    express = "express"


class PaymentsConfigBase(SQLModel):
    provider: PaymentProviderEnum
    enabled: bool = False
    active: bool = False
    mode: PaymentsModeEnum = PaymentsModeEnum.standard
    # Stripe: the connected account id. Bold/OpenPay: unused (their
    # credentials are platform-level, in config.yaml/env — see
    # config/config.py InternalBoldConfig / InternalOpenPayConfig).
    provider_specific_id: Optional[str] = None
    provider_config: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON, nullable=True))


class PaymentsConfig(PaymentsConfigBase, table=True):
    __tablename__ = "paymentsconfig"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    enabled: bool = Field(sa_column=Column(Boolean, nullable=False, default=False))
    active: bool = Field(sa_column=Column(Boolean, nullable=False, default=False))
    creation_date: str = ""
    update_date: str = ""


class PaymentsConfigCreate(SQLModel):
    provider: PaymentProviderEnum
    enabled: bool = True


class PaymentsConfigRead(PaymentsConfigBase):
    id: int
    org_id: int
    creation_date: str
    update_date: str
