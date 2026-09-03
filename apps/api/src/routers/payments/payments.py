from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.payments.config import (
    BoldCredentialsUpdate,
    PaymentProviderEnum,
    PaymentsConfigRead,
)
from src.db.payments.enrollments import PaymentsEnrollment, PaymentsEnrollmentRead
from src.db.payments.groups import (
    PaymentsGroupCreate,
    PaymentsGroupRead,
    PaymentsGroupUpdate,
)
from src.db.payments.offers import (
    PaymentsOfferCreate,
    PaymentsOfferRead,
    PaymentsOfferUpdate,
)
from src.db.users import PublicUser
from src.security.auth import get_current_user
from src.security.recaptcha import verify_recaptcha
from src.security.superadmin import is_user_superadmin
from src.services.payments import config as config_service
from src.services.payments import enrollments as enrollments_service
from src.services.payments import groups as groups_service
from src.services.payments import offers as offers_service
from src.services.payments.providers import ensure_providers_registered
from src.services.payments.providers.base import WebhookVerificationError, get_provider
from src.services.security.rate_limiting import get_client_ip

router = APIRouter()
public_router = APIRouter()


async def _process_provider_webhook(
    request: Request,
    provider_name: PaymentProviderEnum,
    db_session: AsyncSession,
):
    ensure_providers_registered()
    provider = get_provider(provider_name)

    raw_body = await request.body()
    headers = {k: v for k, v in request.headers.items()}

    try:
        event = await provider.verify_and_parse_webhook(raw_body, headers, db_session)
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    if event is None:
        return {"ok": True, "status": "ignored"}

    enrollment = (await db_session.execute(
        select(PaymentsEnrollment).where(PaymentsEnrollment.id == event.enrollment_id)
    )).scalars().first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    last_event_id = (enrollment.provider_specific_data or {}).get("last_provider_event_id")
    if last_event_id == event.provider_event_id:
        return {"ok": True, "status": "duplicate"}

    provider_specific_data = {
        **event.provider_specific_data,
        "last_provider_event_id": event.provider_event_id,
    }
    if event.outcome == "activated":
        await enrollments_service.activate_enrollment(event.enrollment_id, db_session, provider_specific_data)
    elif event.outcome == "cancelled":
        await enrollments_service.cancel_enrollment(event.enrollment_id, db_session, provider_specific_data)
    elif event.outcome == "failed":
        await enrollments_service.fail_enrollment(event.enrollment_id, db_session, provider_specific_data)
    elif event.outcome == "refunded":
        await enrollments_service.refund_enrollment(event.enrollment_id, db_session, provider_specific_data)

    return {"ok": True, "status": event.outcome}


# --- Config -------------------------------------------------------------

@router.get("/{org_id}/config", response_model=list[PaymentsConfigRead], tags=["payments"])
async def api_get_payment_configs(
    *, request: Request, org_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await config_service.get_payment_configs(request, org_id, current_user, db_session)


@router.post("/{org_id}/config", response_model=PaymentsConfigRead, tags=["payments"])
async def api_create_payment_config(
    *, request: Request, org_id: int, provider: PaymentProviderEnum, enabled: bool = True,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await config_service.create_payment_config(request, org_id, provider, enabled, current_user, db_session)


@router.delete("/{org_id}/config", tags=["payments"])
async def api_delete_payment_config(
    *, request: Request, org_id: int, id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    await config_service.delete_payment_config(request, org_id, id, current_user, db_session)
    return {"detail": "Payment configuration deleted"}


@router.put("/{org_id}/config/{id}/credentials", response_model=PaymentsConfigRead, tags=["payments"])
async def api_update_payment_config_credentials(
    *, request: Request, org_id: int, id: int, credentials: BoldCredentialsUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    """Store payment-gateway API keys entered from the dashboard (Bold's
    Identity/Secret/Webhook keys today), encrypted at rest. Write-only —
    the response never contains the values, only `credentials_configured`."""
    return await config_service.update_provider_credentials(request, org_id, id, credentials, current_user, db_session)


# --- Offers ---------------------------------------------------------------

@router.get("/{org_id}/offers", response_model=list[PaymentsOfferRead], tags=["payments"])
async def api_get_offers(
    *, request: Request, org_id: int, page: int = 1, limit: int = 20,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await offers_service.get_offers(request, org_id, current_user, db_session, page, limit)


@router.post("/{org_id}/offers", response_model=PaymentsOfferRead, tags=["payments"])
async def api_create_offer(
    *, request: Request, org_id: int, offer_object: PaymentsOfferCreate, payments_config_id: int | None = None,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await offers_service.create_offer(request, org_id, offer_object, current_user, db_session, payments_config_id)


@router.get("/{org_id}/offers/{offer_id}", response_model=PaymentsOfferRead, tags=["payments"])
async def api_get_offer(
    *, request: Request, org_id: int, offer_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await offers_service.get_offer(request, org_id, offer_id, current_user, db_session)


@router.put("/{org_id}/offers/{offer_id}", response_model=PaymentsOfferRead, tags=["payments"])
async def api_update_offer(
    *, request: Request, org_id: int, offer_id: int, offer_object: PaymentsOfferUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await offers_service.update_offer(request, org_id, offer_id, offer_object, current_user, db_session)


@router.delete("/{org_id}/offers/{offer_id}", tags=["payments"])
async def api_archive_offer(
    *, request: Request, org_id: int, offer_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    await offers_service.archive_offer(request, org_id, offer_id, current_user, db_session)
    return {"detail": "Offer archived"}


@router.post("/{org_id}/offers/{offer_id}/resources", tags=["payments"])
async def api_add_offer_resource(
    *, request: Request, org_id: int, offer_id: int, resource_uuid: str,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    await offers_service.add_resource_to_offer(request, org_id, offer_id, resource_uuid, current_user, db_session)
    return {"detail": "Resource added"}


@router.delete("/{org_id}/offers/{offer_id}/resources", tags=["payments"])
async def api_remove_offer_resource(
    *, request: Request, org_id: int, offer_id: int, resource_uuid: str,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    await offers_service.remove_resource_from_offer(request, org_id, offer_id, resource_uuid, current_user, db_session)
    return {"detail": "Resource removed"}


@router.post("/{org_id}/offers/{offer_uuid}/checkout", tags=["payments"])
async def api_create_checkout(
    *, request: Request, org_id: int, offer_uuid: str, redirect_uri: str,
    recaptcha_token: str | None = None,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    """Provider-agnostic checkout: looks up the org's active PaymentsConfig
    and dispatches to that provider's create_checkout(). Returns
    {checkout_url}. 501 if no Bold/OpenPay/Stripe provider is both
    configured AND implemented yet."""
    from src.db.payments.config import PaymentsConfig
    from src.security.rbac.rbac import authorization_verify_if_user_is_anon
    from src.services.payments.providers.base import PaymentProviderError

    if not await verify_recaptcha(recaptcha_token, "CHECKOUT", get_client_ip(request)):
        raise HTTPException(status_code=403, detail="Verification failed. Please try again.")

    await authorization_verify_if_user_is_anon(current_user.id)

    offer = await offers_service._get_offer_or_404(offer_uuid, org_id, db_session)
    if offer.is_archived:
        raise HTTPException(status_code=404, detail="Offer not found")

    config = (await db_session.execute(
        select(PaymentsConfig).where(PaymentsConfig.id == offer.payments_config_id, PaymentsConfig.active == True)
    )).scalars().first()
    if not config:
        raise HTTPException(status_code=400, detail="This offer's payment provider is not active")

    enrollment = await enrollments_service.create_pending_enrollment(offer, current_user.id, org_id, config.provider, db_session)

    ensure_providers_registered()
    try:
        provider = get_provider(config.provider)
    except PaymentProviderError as e:
        raise HTTPException(status_code=501, detail=str(e))

    checkout_url = await provider.create_checkout(offer, enrollment, redirect_uri, current_user, db_session)
    return {"checkout_url": checkout_url}


# --- Groups -----------------------------------------------------------------

@router.get("/{org_id}/groups", response_model=list[PaymentsGroupRead], tags=["payments"])
async def api_get_groups(
    *, request: Request, org_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await groups_service.get_groups(request, org_id, current_user, db_session)


@router.post("/{org_id}/groups", response_model=PaymentsGroupRead, tags=["payments"])
async def api_create_group(
    *, request: Request, org_id: int, group_object: PaymentsGroupCreate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await groups_service.create_group(request, org_id, group_object, current_user, db_session)


@router.put("/{org_id}/groups/{group_id}", response_model=PaymentsGroupRead, tags=["payments"])
async def api_update_group(
    *, request: Request, org_id: int, group_id: int, group_object: PaymentsGroupUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await groups_service.update_group(request, org_id, group_id, group_object, current_user, db_session)


@router.delete("/{org_id}/groups/{group_id}", tags=["payments"])
async def api_delete_group(
    *, request: Request, org_id: int, group_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    await groups_service.delete_group(request, org_id, group_id, current_user, db_session)
    return {"detail": "Group deleted"}


@router.get("/{org_id}/groups/{group_id}/resources", response_model=list[str], tags=["payments"])
async def api_get_group_resources(
    *, request: Request, org_id: int, group_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await groups_service.get_group_resources(request, org_id, group_id, current_user, db_session)


@router.post("/{org_id}/groups/{group_id}/resources", tags=["payments"])
async def api_add_group_resource(
    *, request: Request, org_id: int, group_id: int, resource_uuid: str,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    await groups_service.add_resource_to_group(request, org_id, group_id, resource_uuid, current_user, db_session)
    return {"detail": "Resource added"}


@router.delete("/{org_id}/groups/{group_id}/resources", tags=["payments"])
async def api_remove_group_resource(
    *, request: Request, org_id: int, group_id: int, resource_uuid: str,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    await groups_service.remove_resource_from_group(request, org_id, group_id, resource_uuid, current_user, db_session)
    return {"detail": "Resource removed"}


@router.post("/{org_id}/groups/{group_id}/sync", response_model=PaymentsGroupRead, tags=["payments"])
async def api_sync_group_usergroup(
    *, request: Request, org_id: int, group_id: int, usergroup_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await groups_service.sync_group_usergroup(request, org_id, group_id, usergroup_id, current_user, db_session)


@router.delete("/{org_id}/groups/{group_id}/sync", response_model=PaymentsGroupRead, tags=["payments"])
async def api_unsync_group_usergroup(
    *, request: Request, org_id: int, group_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await groups_service.unsync_group_usergroup(request, org_id, group_id, current_user, db_session)


# --- Customers / enrollments --------------------------------------------

@router.get("/{org_id}/customers", tags=["payments"])
async def api_get_customers(
    *, request: Request, org_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await enrollments_service.get_org_customers(request, org_id, current_user, db_session)


@router.get("/{org_id}/enrollments/mine", response_model=list[PaymentsEnrollmentRead], tags=["payments"])
async def api_get_my_enrollments(
    *, org_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    return await enrollments_service.get_user_enrollments(org_id, current_user, db_session)


# --- Debug (superadmin-only) — manually flip an enrollment to test the ---
# --- grant-access path before any real provider is wired in. ------------

@router.post("/{org_id}/enrollments/{enrollment_id}/debug-activate", response_model=PaymentsEnrollmentRead, tags=["payments"])
async def api_debug_activate_enrollment(
    *, org_id: int, enrollment_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_current_user),
):
    if not await is_user_superadmin(current_user.id, db_session):
        raise HTTPException(status_code=403, detail="Superadmin only")
    from src.db.payments.enrollments import PaymentsEnrollmentRead as _Read
    enrollment = await enrollments_service.activate_enrollment(enrollment_id, db_session)
    return _Read.model_validate(enrollment)


# --- Public (no auth) --------------------------------------------------

@public_router.get("/{org_id}/offers/{offer_id}/public", response_model=PaymentsOfferRead, tags=["payments"])
async def api_get_public_offer(
    *, org_id: int, offer_id: str,
    db_session: AsyncSession = Depends(get_db_session),
):
    return await offers_service.get_public_offer(org_id, offer_id, db_session)


@public_router.get("/{org_id}/offers/public-listing", response_model=list[PaymentsOfferRead], tags=["payments"])
async def api_get_public_offers_listing(
    *, org_id: int,
    db_session: AsyncSession = Depends(get_db_session),
):
    return await offers_service.get_public_offers_listing(org_id, db_session)


@public_router.get("/{org_id}/offers/by-resource", response_model=list[PaymentsOfferRead], tags=["payments"])
async def api_get_offers_by_resource(
    *, org_id: int, resource_uuid: str,
    db_session: AsyncSession = Depends(get_db_session),
):
    return await offers_service.get_offers_by_resource(org_id, resource_uuid, db_session)


@public_router.post("/webhooks/openpay", tags=["payments"])
async def api_openpay_webhook(
    *, request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    return await _process_provider_webhook(request, PaymentProviderEnum.OPENPAY, db_session)


@public_router.post("/webhooks/bold", tags=["payments"])
async def api_bold_webhook(
    *, request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    return await _process_provider_webhook(request, PaymentProviderEnum.BOLD, db_session)
