from typing import Optional
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class PaymentsGroupBase(SQLModel):
    name: str
    description: Optional[str] = ""


class PaymentsGroup(PaymentsGroupBase, table=True):
    __tablename__ = "paymentsgroup"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    # Set by POST .../groups/{group_id}/sync?usergroup_id=. Buying an offer
    # that references this group also adds the buyer to this UserGroup —
    # e.g. to grant membership in a pre-existing "community" UserGroup that
    # isn't itself modeled as a PaymentsGroupResource. Nullable: a group can
    # exist purely as a resource bundle with no extra UserGroup side effect.
    usergroup_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("usergroup.id", ondelete="SET NULL"), nullable=True),
    )
    creation_date: str = ""
    update_date: str = ""


class PaymentsGroupCreate(PaymentsGroupBase):
    pass


class PaymentsGroupUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PaymentsGroupRead(PaymentsGroupBase):
    id: int
    org_id: int
    usergroup_id: Optional[int] = None
    creation_date: str
    update_date: str


class PaymentsGroupResource(SQLModel, table=True):
    __tablename__ = "paymentsgroupresource"

    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(
        sa_column=Column(Integer, ForeignKey("paymentsgroup.id", ondelete="CASCADE"), nullable=False)
    )
    resource_uuid: str = ""
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
