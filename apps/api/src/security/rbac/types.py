"""
RBAC Types and Enums

This module defines the core types and enums used throughout the RBAC system.
"""

from enum import Enum

from pydantic import BaseModel


class AccessAction(str, Enum):
    """Actions that can be performed on resources."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


class AccessContext(str, Enum):
    """Context in which access is being checked."""
    PUBLIC_VIEW = "public_view"   # Respects public/published flags
    DASHBOARD = "dashboard"       # Admins/authors see everything


class AccessDecision(BaseModel):
    """
    Result of an access check with detailed information about why access was granted/denied.

    This provides auditability - you can see exactly why a user was granted or denied access.
    """
    allowed: bool
    reason: str
    via_usergroup: bool = False
    via_authorship: bool = False
    via_role: bool = False
    via_admin: bool = False
    via_public: bool = False
    resource_uuid: str | None = None
    user_id: int | None = None
    action: str | None = None
    context: str | None = None
    # Set when access was denied specifically because the resource is gated by
    # a PaymentsOffer's usergroup — lets the caller raise 402 with offer data
    # (so the frontend can render a PaymentWall) instead of a plain 403.
    offer: dict | None = None


class ResourceConfig(BaseModel):
    """
    Configuration for a resource type.

    This allows the RBAC system to handle different resource types with different
    characteristics (e.g., some have published field, some support authorship).
    """
    resource_type: str
    uuid_prefix: str
    has_published_field: bool
    supports_usergroups: bool
    supports_authorship: bool

    # Table/model info for lookups
    model_name: str | None = None
    uuid_field: str | None = None

    # Parent resource configuration (for child resources like chapters, episodes)
    # If set, access is delegated to the parent resource
    parent_resource_type: str | None = None
    parent_id_field: str | None = None  # e.g., "course_id" for chapters
