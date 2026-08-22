from .consent_service import consent_service, ConsentService
from .credential_service import credential_service, CredentialService
from .document_storage import document_storage_service, SecureDocumentStorageService
from .identity_service import identity_service, IdentityService
from .kyc_service import kyc_service, KYCService
from .provider_base import (
    IdentityVerificationProvider,
    DevKYCProvider,
    provider_registry,
)

__all__ = [
    "consent_service",
    "ConsentService",
    "credential_service",
    "CredentialService",
    "document_storage_service",
    "SecureDocumentStorageService",
    "identity_service",
    "IdentityService",
    "kyc_service",
    "KYCService",
    "IdentityVerificationProvider",
    "DevKYCProvider",
    "provider_registry",
]
