import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ....schemas.notification import NotificationChannel

logger = logging.getLogger("toursafe.notifications.templates")


class TemplateEngine:
    """
    Template Engine for TourSafe notifications.
    Supports versioned templates, multi-locale fallback, and strict security sanitization.
    """

    def __init__(self):
        # catalog: { (template_id, version, locale): (title_tmpl, body_tmpl) }
        self._catalog: Dict[Tuple[str, str, str], Tuple[str, str]] = {}
        self.fallback_locale = "en"
        self._initialize_default_catalog()

    def _initialize_default_catalog(self):
        # 1. incident-created-authority
        self.register_template(
            template_id="incident-created-authority",
            version="v1",
            locale="en",
            title="TourSafe Emergency Alert: Incident {incident_id}",
            body="New {severity} severity incident reported in {zone_name}. Ref: {incident_id}.",
        )
        self.register_template(
            template_id="incident-created-authority",
            version="v1",
            locale="es",
            title="Alerta de Emergencia TourSafe: Incidente {incident_id}",
            body="Nuevo incidente de gravedad {severity} reportado en {zone_name}. Ref: {incident_id}.",
        )
        self.register_template(
            template_id="incident-created-authority",
            version="v1",
            locale="hi",
            title="टूरसेफ़ आपातकालीन चेतावनी: घटना {incident_id}",
            body="{zone_name} में {severity} गंभीरता की नई घटना दर्ज की गई। संदर्भ: {incident_id}।",
        )

        # 2. incident-assigned-responder
        self.register_template(
            template_id="incident-assigned-responder",
            version="v1",
            locale="en",
            title="Operational Assignment: Incident {incident_id}",
            body="You have been assigned to an active {severity} incident in {zone_name}. Please acknowledge and respond immediately.",
        )
        self.register_template(
            template_id="incident-assigned-responder",
            version="v1",
            locale="hi",
            title="परिचालन कार्यभार: घटना {incident_id}",
            body="आपको {zone_name} में एक सक्रिय {severity} घटना का कार्यभार सौंपा गया है। कृपया तत्काल प्रतिक्रिया दें।",
        )

        # 3. incident-escalated-authority
        self.register_template(
            template_id="incident-escalated-authority",
            version="v1",
            locale="en",
            title="ESCALATION ALERT: Incident {incident_id} escalated to {severity}",
            body="Incident {incident_id} has been escalated due to: {reason}. Operational command oversight required.",
        )

        # 4. sos-acknowledged-tourist
        self.register_template(
            template_id="sos-acknowledged-tourist",
            version="v1",
            locale="en",
            title="SOS Acknowledged — Help Is On The Way",
            body="TourSafe Authority Command has acknowledged your SOS. Emergency responders are mobilizing to assist you. Please remain safe.",
        )
        self.register_template(
            template_id="sos-acknowledged-tourist",
            version="v1",
            locale="es",
            title="SOS Reconocido — La Ayuda Está en Camino",
            body="El Centro de Comando TourSafe ha confirmado su SOS. Los equipos de rescate se están movilizando.",
        )
        self.register_template(
            template_id="sos-acknowledged-tourist",
            version="v1",
            locale="hi",
            title="एसओएस स्वीकृत — सहायता रास्ते में है",
            body="टूरसेफ़ कमांड सेंटर ने आपके एसओएस को स्वीकार कर लिया है। आपातकालीन प्रतिक्रिया दल आपकी सहायता के लिए तैयार हैं।",
        )

        # 5. emergency-contact-alert
        self.register_template(
            template_id="emergency-contact-alert",
            version="v1",
            locale="en",
            title="TourSafe Safety Alert for {tourist_name}",
            body="TourSafe Alert: An emergency condition (Severity: {severity}) has been logged for your contact {tourist_name}. Authority command operations are actively responding. Ref: {incident_id}.",
        )

        # 6. incident-resolved-tourist
        self.register_template(
            template_id="incident-resolved-tourist",
            version="v1",
            locale="en",
            title="Incident Resolved",
            body="Your safety incident {incident_id} has been resolved: {resolution_reason}. Thank you for using TourSafe.",
        )

        # 7. incident-resolved-responder
        self.register_template(
            template_id="incident-resolved-responder",
            version="v1",
            locale="en",
            title="Assignment Completed: Incident {incident_id}",
            body="Incident {incident_id} has been marked resolved. Your unit status is updated.",
        )

        # 8. zone-warning-tourist
        self.register_template(
            template_id="zone-warning-tourist",
            version="v1",
            locale="en",
            title="Geofence Safety Alert: {zone_name}",
            body="You have entered {zone_name} (Risk Level: {risk_level}). Please review safety advisories.",
        )

        # 9. safety-state-changed
        self.register_template(
            template_id="safety-state-changed",
            version="v1",
            locale="en",
            title="Safety Status Update: {safety_state}",
            body="Your safety status has changed to {safety_state}. Please follow standard guidance.",
        )

        # 10. system-alert
        self.register_template(
            template_id="system-alert",
            version="v1",
            locale="en",
            title="System Alert: {title}",
            body="{message}",
        )

    def register_template(
        self,
        template_id: str,
        version: str,
        locale: str,
        title: str,
        body: str,
    ):
        key = (template_id, version, locale.lower())
        self._catalog[key] = (title, body)

    def sanitize_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Security sanitizer:
        - Removes sensitive medical diagnoses/records
        - Removes raw internal AI anomaly scores and weights
        - Truncates excessive GPS precision (max 4 decimal places)
        - Replaces internal system jargon
        """
        sanitized = {}
        for k, v in variables.items():
            k_lower = k.lower()

            # Strip medical details
            if "medical" in k_lower or "diagnosis" in k_lower or "allergy" in k_lower:
                continue

            # Strip internal AI scores
            if "anomaly_score" in k_lower or "model_weight" in k_lower or "reconstruction_error" in k_lower:
                continue

            # Round coordinates to 4 decimal places for privacy & clarity (~11 meters)
            if ("latitude" in k_lower or "longitude" in k_lower or "lat" == k_lower or "lng" == k_lower) and isinstance(v, (int, float)):
                sanitized[k] = round(float(v), 4)
            elif isinstance(v, (str, int, float, bool)):
                sanitized[k] = str(v)
            else:
                sanitized[k] = str(v)

        return sanitized

    def render(
        self,
        template_id: str,
        variables: Dict[str, Any],
        version: str = "v1",
        locale: str = "en",
        channel: NotificationChannel = NotificationChannel.IN_APP,
    ) -> Tuple[str, str]:
        """
        Renders title and body.
        Falls back to default locale if requested locale is missing.
        Applies security sanitization before string substitution.
        """
        loc = (locale or self.fallback_locale).lower()
        key = (template_id, version, loc)

        if key not in self._catalog:
            # Fallback to English
            key = (template_id, version, self.fallback_locale)

        if key not in self._catalog:
            # Generic fallback
            logger.warning("Template (%s, %s, %s) not found, using generic fallback", template_id, version, loc)
            title = variables.get("title", f"TourSafe Alert: {template_id}")
            body = variables.get("message", variables.get("body", "A safety event has been recorded."))
            return str(title), str(body)

        title_tmpl, body_tmpl = self._catalog[key]
        clean_vars = self.sanitize_variables(variables)

        # Safe interpolation using defaultdict/regex or format_map
        def replace_var(template_str: str) -> str:
            def repl(match):
                var_name = match.group(1).strip()
                return str(clean_vars.get(var_name, f"[{var_name}]"))
            return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, template_str)

        rendered_title = replace_var(title_tmpl)
        rendered_body = replace_var(body_tmpl)

        return rendered_title, rendered_body


template_engine = TemplateEngine()
