"""Email string translations.

Mirrors the locales declared in `apps/web/lib/languages.ts`. Each value uses
Python `str.format` placeholders. Inputs are HTML-escaped at the call site
before being formatted in.
"""

from typing import Final

SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("en", "es")

# Locales selectable as an organisation's UI language; mirrors
# apps/web/lib/languages.ts. A UI locale need not have an email-translation
# bundle — emails for any locale without one fall back to English (see `t()`).
SUPPORTED_UI_LANGUAGES: Final[tuple[str, ...]] = ("en", "es")

DEFAULT_LANGUAGE: Final[str] = "en"


EMAIL_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "account_creation.subject": "Welcome to BBB Academia, {username}!",
        "account_creation.heading": "Welcome, {username}!",
        "account_creation.body": "Your BBB Academia account is ready. Get started by creating your own organization or joining one.",
        "account_creation.cta": "Get Started",
        "account_creation.footer": "Need help? Visit {academy_link} to learn the basics.",
        "academy_link_text": "BBB Academia Academy",

        "org_created.subject": "Your organization {org_name} is ready",
        "org_created.heading": "{org_name} is live!",
        "org_created.body": "Your new organization is set up and ready. Invite your team, create your first course, and make it yours.",
        "org_created.cta": "Open your dashboard",
        "org_created.footer": "You're receiving this because you created an organization on BBB Academia.",

        "org_deleted.subject": "Your organization {org_name} was deleted",
        "org_deleted.heading": "{org_name} has been deleted",
        "org_deleted.body": "Your organization and all of its content have been permanently removed from BBB Academia. If this wasn't you, contact support right away.",
        "org_deleted.footer": "You're receiving this because you were an admin of this organization.",

        "account_deleted.subject": "Your BBB Academia account was deleted",
        "account_deleted.heading": "Your account has been deleted",
        "account_deleted.body": "Your BBB Academia account and personal data have been permanently removed. We're sorry to see you go. If this wasn't you, contact support right away.",
        "account_deleted.footer": "This is a confirmation that your account was deleted.",

        "password_reset.subject": "Reset your password",
        "password_reset.heading": "Reset your password",
        "password_reset.body": "Hi {username}, we received a request to reset your password. Use the code below or click the button.",
        "password_reset.cta": "Reset Password",
        "password_reset.footer_org": "If you didn't request a password reset, you can safely ignore this email. This link will expire shortly.",
        "password_reset.footer_platform": "If you didn't request a password reset, you can safely ignore this email. This link will expire in 1 hour.",

        "invitation.subject": "You've been invited to join {org_name}",
        "invitation.heading": "You've been invited!",
        "invitation.intro": "<strong>@{inviter}</strong> has invited you to join <strong>{org_name}</strong> on BBB Academia.",
        "invitation.code_hint": "Use the invite code above, or click the button below to sign up.",
        "invitation.no_code_hint": "Click the button below to get started.",
        "invitation.cta": "Join {org_name}",
        "invitation.footer": "This invitation was sent by @{inviter}. If you weren't expecting this, you can safely ignore it.",

        "role_changed.subject": "Your role in {org_name} has been updated",
        "role_changed.heading": "Your role has been updated",
        "role_changed.body_1": "Hi {username}, your role in <strong>{org_name}</strong> has been changed to <strong>{role}</strong>.",
        "role_changed.body_2": "This may affect what you can access and manage within the organization. If you have any questions, please reach out to your organization administrator.",
        "role_changed.footer": "You received this email because your role was changed in {org_name} on BBB Academia.",

        "email_verification.subject": "Verify your email address",
        "email_verification.heading": "Verify your email",
        "email_verification.body": "Hi {username}, welcome to BBB Academia! Click the button below to verify your email address and activate your account.",
        "email_verification.cta": "Verify Email Address",
        "email_verification.copy_paste": "Or copy and paste this link:",
        "email_verification.footer": "This link expires in 1 hour. If you didn't create a BBB Academia account, you can safely ignore this email.",
    },
    "es": {
        "account_creation.subject": "¡Bienvenido a BBB Academia, {username}!",
        "account_creation.heading": "¡Bienvenido, {username}!",
        "account_creation.body": "Tu cuenta de BBB Academia está lista. Empieza creando tu propia organización o uniéndote a una.",
        "account_creation.cta": "Empezar",
        "account_creation.footer": "¿Necesitas ayuda? Visita {academy_link} para aprender lo básico.",
        "academy_link_text": "BBB Academia Academy",

        "password_reset.subject": "Restablece tu contraseña",
        "password_reset.heading": "Restablece tu contraseña",
        "password_reset.body": "Hola {username}, recibimos una solicitud para restablecer tu contraseña. Usa el código de abajo o haz clic en el botón.",
        "password_reset.cta": "Restablecer contraseña",
        "password_reset.footer_org": "Si no solicitaste restablecer tu contraseña, puedes ignorar este correo. Este enlace caducará pronto.",
        "password_reset.footer_platform": "Si no solicitaste restablecer tu contraseña, puedes ignorar este correo. Este enlace caducará en 1 hora.",

        "invitation.subject": "Te han invitado a unirte a {org_name}",
        "invitation.heading": "¡Te han invitado!",
        "invitation.intro": "<strong>@{inviter}</strong> te ha invitado a unirte a <strong>{org_name}</strong> en BBB Academia.",
        "invitation.code_hint": "Usa el código de invitación de arriba, o haz clic en el botón para registrarte.",
        "invitation.no_code_hint": "Haz clic en el botón de abajo para empezar.",
        "invitation.cta": "Unirse a {org_name}",
        "invitation.footer": "Esta invitación fue enviada por @{inviter}. Si no la esperabas, puedes ignorarla.",

        "role_changed.subject": "Tu rol en {org_name} ha sido actualizado",
        "role_changed.heading": "Tu rol ha sido actualizado",
        "role_changed.body_1": "Hola {username}, tu rol en <strong>{org_name}</strong> ha cambiado a <strong>{role}</strong>.",
        "role_changed.body_2": "Esto puede afectar lo que puedes ver y gestionar dentro de la organización. Si tienes preguntas, contacta al administrador de tu organización.",
        "role_changed.footer": "Recibiste este correo porque tu rol fue cambiado en {org_name} en BBB Academia.",

        "email_verification.subject": "Verifica tu dirección de correo",
        "email_verification.heading": "Verifica tu correo",
        "email_verification.body": "Hola {username}, ¡bienvenido a BBB Academia! Haz clic en el botón para verificar tu dirección de correo y activar tu cuenta.",
        "email_verification.cta": "Verificar correo",
        "email_verification.copy_paste": "O copia y pega este enlace:",
        "email_verification.footer": "Este enlace caduca en 1 hora. Si no creaste una cuenta de BBB Academia, puedes ignorar este correo.",
    },
}


def normalize_language(lang: str | None) -> str:
    """Return a supported locale code, falling back to English."""
    if not lang:
        return DEFAULT_LANGUAGE
    code = lang.split("-")[0].lower()
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def t(lang: str | None, key: str, **fmt) -> str:
    """Translate `key` for `lang`, falling back to English on missing locale or key."""
    code = normalize_language(lang)
    bundle = EMAIL_TRANSLATIONS.get(code, EMAIL_TRANSLATIONS[DEFAULT_LANGUAGE])
    template = bundle.get(key) or EMAIL_TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    try:
        return template.format(**fmt)
    except (KeyError, IndexError):
        return template
