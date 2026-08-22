from datetime import datetime, timezone
import logging
import re
import time
from typing import Any, Dict, List, Optional

from ....schemas.integrations import (
    IntegrationConfig,
    IntegrationHealthStatus,
    IntegrationStatus,
    IntegrationType,
    TranslationResult,
)
from .base import IntegrationAdapter

logger = logging.getLogger("toursafe.integrations.adapters.translation")

# Patterns for safety critical tokens that MUST NOT be translated
TECH_TOKEN_PATTERNS = [
    re.compile(r"INC-\d{4}-\d+", re.IGNORECASE),
    re.compile(r"SOS-\d+", re.IGNORECASE),
    re.compile(r"UNIT-[A-Z0-9]+", re.IGNORECASE),
    re.compile(r"\b\d{1,3}\.\d{4,8},\s*-?\d{1,3}\.\d{4,8}\b"),  # Coordinates
    re.compile(r"https?://\S+", re.IGNORECASE),
]


class TranslationAdapter(IntegrationAdapter):
    """
    Translation Adapter Interface.
    Enforces token preservation (incident IDs, coordinates, callsigns) and dual original/translated outputs.
    """

    def __init__(
        self,
        provider_name: str = "DEV_TRANSLATION_ADAPTER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.TRANSLATION,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(provider_name=provider_name, integration_type=IntegrationType.TRANSLATION),
        )

    @property
    def capabilities(self) -> List[str]:
        return ["text_translation", "language_detection", "multilingual_safety_phrases", "token_masking"]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 11.0
        status.is_healthy = True
        status.detail = f"Translation Engine '{self.provider_name}' operational"
        return status

    async def translate(
        self,
        text: str,
        target_language: str = "en",
        source_language: Optional[str] = None,
    ) -> TranslationResult:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        # Extract tokens that must remain untranslated
        preserved_tokens = []
        for pat in TECH_TOKEN_PATTERNS:
            for match in pat.finditer(text):
                preserved_tokens.append(match.group(0))

        # Dev / Offline Translation Mock mapping for emergency phrases
        src_lang = source_language or "auto"
        tgt = target_language.lower()
        translated_text = text

        # Simple emergency translation glossary for tests
        glossary = {
            "help me": {"hi": "मेरी मदद करो (Help me)", "fr": "Aidez-moi (Help me)", "es": "Ayúdeme (Help me)", "ru": "Помогите мне (Help me)"},
            "medical emergency": {"hi": "चिकित्सा आपातकाल (Medical Emergency)", "fr": "Urgence médicale", "es": "Emergencia médica"},
            "i am safe": {"hi": "मैं सुरक्षित हूँ (I am safe)", "fr": "Je suis en sécurité", "es": "Estoy a salvo"},
        }

        clean_lower = text.strip().lower()
        if clean_lower in glossary and tgt in glossary[clean_lower]:
            translated_text = glossary[clean_lower][tgt]
        else:
            if tgt != "en" and src_lang == "en":
                translated_text = f"[{tgt.upper()}] {text}"
            elif tgt == "en" and src_lang != "en":
                translated_text = f"[EN] {text}"

        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return TranslationResult(
            original_text=text,
            translated_text=translated_text,
            source_language=src_lang,
            target_language=tgt,
            provider=self.provider_name,
            confidence=0.98,
            untranslated_tokens=preserved_tokens,
        )
