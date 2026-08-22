import pytest
from app.services.integrations.adapters import (
    DevMapsAdapter,
    DevWeatherAdapter,
    DocumentAdapter,
    EmailAdapter,
    EmergencyServiceAdapter,
    GovernmentAuthorityAdapter,
    IdentityProviderAdapter,
    PushAdapter,
    SMSAdapter,
    TourismDataAdapter,
    TranslationAdapter,
    VoiceAdapter,
)


@pytest.mark.asyncio
async def test_01_maps_adapter_geocoding_and_routing():
    adapter = DevMapsAdapter()
    await adapter.initialize()

    # Geocode
    geo = await adapter.geocode("Calangute Beach")
    assert geo.latitude > 0.0
    assert geo.longitude > 0.0
    assert "Goa" in geo.formatted_address
    assert geo.confidence >= 0.9

    # Reverse Geocode
    rev = await adapter.reverse_geocode(15.5439, 73.7554)
    assert "Goa" in rev.formatted_address

    # Calculate Route
    route = await adapter.calculate_route(
        origin=[73.7554, 15.5439],
        destination=[73.8278, 15.4989],
    )
    assert route.distance_meters > 0.0
    assert route.duration_seconds > 0.0
    assert len(route.steps) >= 2
    assert route.geometry_geojson["type"] == "LineString"


@pytest.mark.asyncio
async def test_02_communication_adapters():
    sms = SMSAdapter("DEV_SMS_ADAPTER")
    voice = VoiceAdapter("DEV_VOICE_ADAPTER")
    email = EmailAdapter("DEV_EMAIL_ADAPTER")
    push = PushAdapter("DEV_PUSH_ADAPTER")

    # SMS
    sms_res = await sms.send_sms("+919876543210", "TourSafe Emergency Alert")
    assert sms_res["status"] == "SENT"
    assert "sms_" in sms_res["provider_message_id"]

    # Voice
    voice_res = await voice.initiate_call("+919876543210", "Critical alert broadcast")
    assert voice_res["status"] == "QUEUED"
    assert "call_" in voice_res["provider_call_id"]

    # Email
    mail_res = await email.send_email("tourist@example.com", "Safety Update", "<p>Safe</p>")
    assert mail_res["status"] == "SENT"

    # Push
    push_res = await push.send_push(["device_tok_1", "device_tok_2"], "Safety Alert", "Hazard warning")
    assert push_res["status"] == "SENT"
    assert push_res["device_count"] == 2


@pytest.mark.asyncio
async def test_03_identity_kyc_adapter():
    identity = IdentityProviderAdapter("DEV_IDENTITY_PROVIDER")
    sub = await identity.submit_verification(
        tourist_id="tourist_100",
        document_type="PASSPORT",
        masked_identifier="****5432",
    )
    assert sub["status"] == "PENDING"
    assert "KYC-EXT-" in sub["provider_reference"]

    status_res = await identity.check_status(sub["provider_reference"])
    assert status_res["status"] == "VERIFIED"
    assert status_res["verified"] is True


@pytest.mark.asyncio
async def test_04_weather_adapter():
    weather = DevWeatherAdapter()
    curr = await weather.get_current_weather(15.4989, 73.8278)
    assert curr.temperature_celsius > 0
    assert curr.wind_speed_kmh >= 0
    assert curr.provider == "DEV_WEATHER_PROVIDER"
    assert "TourSafe Dev Weather Engine" in curr.attribution

    alerts = await weather.get_severe_alerts(15.4989, 73.8278)
    assert isinstance(alerts, list)


@pytest.mark.asyncio
async def test_05_translation_adapter_safety_token_protection():
    trans = TranslationAdapter("DEV_TRANSLATION_ADAPTER")

    # Should translate emergency phrase but preserve incident IDs, coordinates, and callsigns
    input_text = "Medical emergency at 15.5439, 73.7554 for incident INC-2026-001 with UNIT-BRAVO"
    res = await trans.translate(input_text, target_language="hi")

    assert res.target_language == "hi"
    assert "INC-2026-001" in res.untranslated_tokens
    assert "UNIT-BRAVO" in res.untranslated_tokens


@pytest.mark.asyncio
async def test_06_emergency_cad_adapter():
    cad = EmergencyServiceAdapter("DEV_EMERGENCY_CAD_ADAPTER")
    req = await cad.create_emergency_request(
        toursafe_incident_id="INC-2026-888",
        severity="CRITICAL",
        incident_type="DROWNING_RESCUE",
        latitude=15.5439,
        longitude=73.7554,
        location_description="Calangute Shore",
        description="Tourist pulled from water",
        contact_name="John Doe",
        responder_units_requested=2,
    )
    assert "CAD-" in req.external_incident_id
    assert req.status == "DISPATCHED"
    assert req.contact_name_masked == "John D."  # PII minimization


@pytest.mark.asyncio
async def test_07_government_tourism_document_adapters():
    gov = GovernmentAuthorityAdapter("DEV_GOVERNMENT_ADAPTER")
    tourism = TourismDataAdapter("DEV_TOURISMDATA_ADAPTER")
    doc_vault = DocumentAdapter("DEV_DOCUMENT_VAULT")

    # Government advisories
    advs = await gov.query_public_advisories("GOA_NORTH")
    assert len(advs) > 0
    assert "Directorate of Tourism" in advs[0]["authority"]

    # Tourism attractions
    attrs = await tourism.query_attractions("Goa")
    assert len(attrs) >= 2
    assert attrs[0]["safety_tier"] == "SAFE"

    # Document upload
    doc_res = await doc_vault.upload_document(
        file_bytes=b"Sample PDF bytes",
        file_name="passport_scan.pdf",
        mime_type="application/pdf",
    )
    assert doc_res["success"] is True
    assert "docs/vault/" in doc_res["storage_key"]
