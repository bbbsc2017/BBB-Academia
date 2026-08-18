from enum import Enum
from typing import Optional
from uuid import uuid4
from sqlalchemy import Column, ForeignKey, Integer, Boolean, Float
from sqlmodel import Field, SQLModel
from src.db.payments.config import PaymentProviderEnum


class OfferTypeEnum(str, Enum):
    one_time = "one_time"
    subscription = "subscription"


class PriceTypeEnum(str, Enum):
    fixed_price = "fixed_price"
    customer_choice = "customer_choice"


class PaymentsOfferBase(SQLModel):
    name: str
    description: Optional[str] = ""
    offer_type: OfferTypeEnum
    price_type: PriceTypeEnum = PriceTypeEnum.fixed_price
    # Comma-separated list, mirrors the frontend's CreateOfferForm textarea.
    benefits: Optional[str] = ""
    amount: float
    currency: str
    is_publicly_listed: bool = True
    # Soft-delete: an archived offer disappears from listings/checkout but its
    # row (and every PaymentsEnrollment referencing it) stays intact — never
    # hard-delete an offer, it would cascade-destroy purchase history.
    is_archived: bool = False


class PaymentsOffer(PaymentsOfferBase, table=True):
    __tablename__ = "paymentsoffer"

    id: Optional[int] = Field(default=None, primary_key=True)
    offer_uuid: str = Field(default_factory=lambda: f"offer_{uuid4()}", unique=True, index=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    payments_config_id: int = Field(
        sa_column=Column(Integer, ForeignKey("paymentsconfig.id", ondelete="CASCADE"), nullable=False)
    )
    # The UserGroup that gates access to every resource behind this offer.
    # check_usergroup_access() in security/rbac/rbac.py reads this via
    # _get_offer_for_usergroup() to raise 402 with offer details, and
    # services/payments/enrollments.py adds/removes UserGroupUser rows here
    # on payment success/cancellation — access control itself never changes.
    usergroup_id: int = Field(
        sa_column=Column(Integer, ForeignKey("usergroup.id", ondelete="CASCADE"), nullable=False)
    )
    # Optional bundle of extra resources (see PaymentsGroup/PaymentsGroupResource).
    # Buying this offer also grants access to everything in the group, and — if
    # the group has its own usergroup_id set via the /sync endpoint — membership
    # in that UserGroup too. Nullable: most offers gate resources directly via
    # PaymentsOfferResource and never need a group.
    payments_group_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("paymentsgroup.id", ondelete="SET NULL"), nullable=True),
    )
    # Provider-side product/plan id (e.g. an OpenPay plan id for subscriptions).
    provider_product_id: Optional[str] = None
    is_publicly_listed: bool = Field(sa_column=Column(Boolean, nullable=False, default=True))
    is_archived: bool = Field(sa_column=Column(Boolean, nullable=False, default=False))
    amount: float = Field(sa_column=Column(Float, nullable=False))
    creation_date: str = ""
    update_date: str = ""


class PaymentsOfferCreate(PaymentsOfferBase):
    payments_group_id: Optional[int] = None
    resource_uuids: Optional[list[str]] = None


class PaymentsOfferUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    offer_type: Optional[OfferTypeEnum] = None
    price_type: Optional[PriceTypeEnum] = None
    benefits: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    is_publicly_listed: Optional[bool] = None


class PaymentsOfferRead(PaymentsOfferBase):
    id: int
    offer_uuid: str
    org_id: int
    payments_config_id: int
    provider: Optional[PaymentProviderEnum] = None
    usergroup_id: int
    payments_group_id: Optional[int] = None
    provider_product_id: Optional[str] = None
    creation_date: str
    update_date: str


# Resources attached directly to an offer (independent of a PaymentsGroup).
# Same `{type}_{uuid}` convention as UserGroupResource.resource_uuid.
class PaymentsOfferResource(SQLModel, table=True):
    __tablename__ = "paymentsofferresource"

    id: Optional[int] = Field(default=None, primary_key=True)
    offer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("paymentsoffer.id", ondelete="CASCADE"), nullable=False)
    )
    resource_uuid: str = ""
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
