from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer
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
    description: str | None = ""
    offer_type: OfferTypeEnum
    price_type: PriceTypeEnum = PriceTypeEnum.fixed_price
    # Comma-separated list, mirrors the frontend's CreateOfferForm textarea.
    benefits: str | None = ""
    amount: float
    currency: str
    is_publicly_listed: bool = True
    # Soft-delete: an archived offer disappears from listings/checkout but its
    # row (and every PaymentsEnrollment referencing it) stays intact — never
    # hard-delete an offer, it would cascade-destroy purchase history.
    is_archived: bool = False


class PaymentsOffer(PaymentsOfferBase, table=True):
    __tablename__ = "paymentsoffer"

    id: int | None = Field(default=None, primary_key=True)
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
    payments_group_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("paymentsgroup.id", ondelete="SET NULL"), nullable=True),
    )
    # Provider-side product/plan id (e.g. an OpenPay plan id for subscriptions).
    provider_product_id: str | None = None
    is_publicly_listed: bool = Field(sa_column=Column(Boolean, nullable=False, default=True))
    is_archived: bool = Field(sa_column=Column(Boolean, nullable=False, default=False))
    amount: float = Field(sa_column=Column(Float, nullable=False))
    creation_date: str = ""
    update_date: str = ""


class PaymentsOfferCreate(PaymentsOfferBase):
    payments_group_id: int | None = None
    resource_uuids: list[str] | None = None


class PaymentsOfferUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    offer_type: OfferTypeEnum | None = None
    price_type: PriceTypeEnum | None = None
    benefits: str | None = None
    amount: float | None = None
    currency: str | None = None
    is_publicly_listed: bool | None = None


class PaymentsOfferRead(PaymentsOfferBase):
    id: int
    offer_uuid: str
    org_id: int
    payments_config_id: int
    provider: PaymentProviderEnum | None = None
    usergroup_id: int
    payments_group_id: int | None = None
    provider_product_id: str | None = None
    creation_date: str
    update_date: str
    # Only populated by get_offers_by_resource (the "what can unlock this
    # course/podcast/etc." listing) — True when the CURRENT caller already
    # has an active enrollment for this offer. Defaults False so every other
    # caller of this model (admin offer list/CRUD, anonymous listings) is
    # unaffected; those never set it and it's meaningless there anyway.
    has_access: bool = False


# Resources attached directly to an offer (independent of a PaymentsGroup).
# Same `{type}_{uuid}` convention as UserGroupResource.resource_uuid.
class PaymentsOfferResource(SQLModel, table=True):
    __tablename__ = "paymentsofferresource"

    id: int | None = Field(default=None, primary_key=True)
    offer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("paymentsoffer.id", ondelete="CASCADE"), nullable=False)
    )
    resource_uuid: str = ""
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
