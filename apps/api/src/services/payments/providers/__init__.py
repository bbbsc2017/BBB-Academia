from src.db.payments.config import PaymentProviderEnum
from src.services.payments.providers.base import register_provider
from src.services.payments.providers.bold import BoldProvider
from src.services.payments.providers.openpay import OpenPayProvider

_REGISTERED = False


def ensure_providers_registered() -> None:
	global _REGISTERED
	if _REGISTERED:
		return
	register_provider(PaymentProviderEnum.BOLD, BoldProvider())
	register_provider(PaymentProviderEnum.OPENPAY, OpenPayProvider())
	_REGISTERED = True
