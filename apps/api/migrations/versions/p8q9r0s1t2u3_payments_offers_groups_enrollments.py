"""Payments: offers, groups, enrollments (Bold/OpenPay support)

Rebuilds the offer/enrollment/group tables that a prior migration
(q6r7s8t9u0v1_offer_uuid, "Drop legacy payments tables") removed along with
the old paymentsproduct/paymentscourse/paymentsuser schema — those tables
belonged to a proprietary EE module that isn't present in this fork, so this
migration defines a first-class OSS replacement instead of restoring the old
shape. `paymentsconfig` (the one payments table that did survive) is
untouched here except for widening `paymentproviderenum`.

1. Add 'BOLD' and 'OPENPAY' to paymentproviderenum (defensively (re)creates
   the type first with checkfirst=True — the original migration that should
   have created it used create_type=False, so a database that never had
   Stripe payments configured may not have it yet).
2. New enums: offertypeenum, pricetypeenum, enrollmentstatusenum.
3. New tables: paymentsoffer, paymentsofferresource, paymentsgroup,
   paymentsgroupresource, paymentsenrollment.

Revision ID: p8q9r0s1t2u3
Revises: c1d2e3f4a5b6
Create Date: 2026-08-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'p8q9r0s1t2u3'
down_revision: str | None = 'c1d2e3f4a5b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- paymentproviderenum: ensure it exists, then widen it --------------
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block; commit
    # first and use IF NOT EXISTS so this is safe to re-run.
    provider_enum = postgresql.ENUM('STRIPE', name='paymentproviderenum', create_type=True)
    provider_enum.create(op.get_bind(), checkfirst=True)
    op.execute("COMMIT")
    op.execute("ALTER TYPE paymentproviderenum ADD VALUE IF NOT EXISTS 'BOLD'")
    op.execute("ALTER TYPE paymentproviderenum ADD VALUE IF NOT EXISTS 'OPENPAY'")

    # --- new enum types ------------------------------------------------------
    offer_type_enum = postgresql.ENUM('one_time', 'subscription', name='offertypeenum', create_type=True)
    offer_type_enum.create(op.get_bind(), checkfirst=True)

    price_type_enum = postgresql.ENUM('fixed_price', 'customer_choice', name='pricetypeenum', create_type=True)
    price_type_enum.create(op.get_bind(), checkfirst=True)

    enrollment_status_enum = postgresql.ENUM(
        'pending', 'active', 'cancelled', 'failed', 'refunded',
        name='enrollmentstatusenum', create_type=True,
    )
    enrollment_status_enum.create(op.get_bind(), checkfirst=True)

    # --- paymentsgroup ---------------------------------------------------
    # Created before paymentsoffer since offers optionally FK into groups.
    op.create_table(
        'paymentsgroup',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('usergroup_id', sa.BigInteger(), nullable=True),
        sa.Column('creation_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('update_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usergroup_id'], ['usergroup.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- paymentsoffer ---------------------------------------------------
    op.create_table(
        'paymentsoffer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('offer_uuid', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('org_id', sa.BigInteger(), nullable=False),
        sa.Column('payments_config_id', sa.BigInteger(), nullable=False),
        sa.Column('usergroup_id', sa.BigInteger(), nullable=False),
        sa.Column('payments_group_id', sa.BigInteger(), nullable=True),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('offer_type', postgresql.ENUM('one_time', 'subscription', name='offertypeenum', create_type=False), nullable=False),
        sa.Column('price_type', postgresql.ENUM('fixed_price', 'customer_choice', name='pricetypeenum', create_type=False), nullable=False),
        sa.Column('benefits', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('provider_product_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('is_publicly_listed', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('creation_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('update_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payments_config_id'], ['paymentsconfig.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usergroup_id'], ['usergroup.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payments_group_id'], ['paymentsgroup.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('offer_uuid'),
    )
    op.create_index('ix_paymentsoffer_offer_uuid', 'paymentsoffer', ['offer_uuid'])

    # --- paymentsofferresource ---------------------------------------------
    op.create_table(
        'paymentsofferresource',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('offer_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_uuid', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('org_id', sa.BigInteger(), nullable=False),
        sa.Column('creation_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(['offer_id'], ['paymentsoffer.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- paymentsgroupresource ----------------------------------------------
    op.create_table(
        'paymentsgroupresource',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_uuid', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('org_id', sa.BigInteger(), nullable=False),
        sa.Column('creation_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['paymentsgroup.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- paymentsenrollment --------------------------------------------------
    op.create_table(
        'paymentsenrollment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('offer_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('org_id', sa.BigInteger(), nullable=False),
        sa.Column('status', postgresql.ENUM(
            'pending', 'active', 'cancelled', 'failed', 'refunded',
            name='enrollmentstatusenum', create_type=False,
        ), nullable=False, server_default='pending'),
        sa.Column('provider', postgresql.ENUM('STRIPE', 'BOLD', 'OPENPAY', name='paymentproviderenum', create_type=False), nullable=False),
        sa.Column('provider_specific_data', sa.JSON(), nullable=True),
        sa.Column('creation_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('update_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(['offer_id'], ['paymentsoffer.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_paymentsenrollment_offer_id', 'paymentsenrollment', ['offer_id'])
    op.create_index('ix_paymentsenrollment_user_id', 'paymentsenrollment', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_paymentsenrollment_user_id', table_name='paymentsenrollment')
    op.drop_index('ix_paymentsenrollment_offer_id', table_name='paymentsenrollment')
    op.drop_table('paymentsenrollment')
    op.drop_table('paymentsofferresource')
    op.drop_index('ix_paymentsoffer_offer_uuid', table_name='paymentsoffer')
    op.drop_table('paymentsoffer')
    op.drop_table('paymentsgroupresource')
    op.drop_table('paymentsgroup')

    op.execute("DROP TYPE IF EXISTS enrollmentstatusenum")
    op.execute("DROP TYPE IF EXISTS pricetypeenum")
    op.execute("DROP TYPE IF EXISTS offertypeenum")
    # Note: PostgreSQL does not support removing individual enum values, so
    # 'BOLD'/'OPENPAY' remain in paymentproviderenum after downgrade.
