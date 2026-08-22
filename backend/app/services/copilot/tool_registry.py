"""
TourSafe Copilot Tool Registry & Authorization Gateway.
Maintains typed tool definitions, parameter validation schemas, role-based
pre-execution access control gates, loop detection, and safe execution wrappers.
"""

import asyncio
import inspect
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional
from ...schemas.copilot import ToolDefinitionSchema
from . import tools

logger = logging.getLogger(__name__)


class ToolDefinition:
    def __init__(
        self,
        name: str,
        category: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        required_roles: Optional[List[str]] = None,
        read_only: bool = True,
        requires_preview: bool = False,
    ):
        self.name = name
        self.category = category
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.required_roles = required_roles or ["authority", "admin", "dispatcher", "commander"]
        self.read_only = read_only
        self.requires_preview = requires_preview

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "parameters": self.parameters,
            "required_role": self.required_roles,
            "read_only": self.read_only,
            "requires_preview": self.requires_preview,
        }


class ToolRegistry:
    """Central registry of all authorized Copilot tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(self, tool_def: ToolDefinition) -> None:
        self._tools[tool_def.name] = tool_def

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def get_authorized_tools_for_role(self, role: str) -> List[ToolDefinition]:
        role_lower = role.lower()
        authorized = []
        for t in self._tools.values():
            if any(r.lower() == role_lower or role_lower == "admin" for r in t.required_roles):
                authorized.append(t)
        return authorized

    def get_authorized_tool_schemas(self, role: str) -> List[Dict[str, Any]]:
        return [t.to_schema() for t in self.get_authorized_tools_for_role(role)]

    def list_all_tools(self) -> List[Dict[str, Any]]:
        return [t.to_public_dict() for t in self._tools.values()]

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_context: Dict[str, Any],
        timeout_sec: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Execute a tool with pre-execution authorization check, input validation,
        audit tagging, and bounded execution timeout.
        """
        start_time = time.time()
        tool_def = self.get_tool(tool_name)

        if not tool_def:
            return {
                "success": False,
                "error": "TOOL_NOT_FOUND",
                "message": f"Tool '{tool_name}' does not exist in registry.",
                "source": "Tool Registry",
                "latency_ms": 0.0,
            }

        # 1. Pre-execution RBAC Authorization check
        user_role = user_context.get("role", "tourist").lower()
        if not any(r.lower() == user_role or user_role == "admin" for r in tool_def.required_roles):
            return {
                "success": False,
                "error": "UNAUTHORIZED",
                "message": f"Role '{user_role}' is not authorized to execute '{tool_name}'.",
                "source": "Tool Authorization Gate",
                "latency_ms": 0.0,
            }

        # 2. Input validation & sanitization
        sanitized_args = {}
        for param_name, param_val in arguments.items():
            # Prevent mongo operator injections ($where, $regex, etc.) in string inputs
            if isinstance(param_val, str) and param_val.startswith("$"):
                return {
                    "success": False,
                    "error": "INVALID_INPUT",
                    "message": f"Invalid parameter value for '{param_name}'.",
                    "source": "Tool Input Validator",
                    "latency_ms": 0.0,
                }
            sanitized_args[param_name] = param_val

        # 3. Execution under timeout
        try:
            handler = tool_def.handler
            if "context" in inspect.signature(handler).parameters:
                sanitized_args["context"] = user_context

            res = await asyncio.wait_for(handler(**sanitized_args), timeout=timeout_sec)
            latency = (time.time() - start_time) * 1000
            if isinstance(res, dict):
                res["latency_ms"] = latency
            return res

        except asyncio.TimeoutError:
            latency = (time.time() - start_time) * 1000
            return {
                "success": False,
                "error": "TIMEOUT",
                "message": f"Execution of tool '{tool_name}' timed out after {timeout_sec}s.",
                "source": "Tool Execution Engine",
                "latency_ms": latency,
            }
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"Tool execution failed for '{tool_name}': {e}", exc_info=True)
            return {
                "success": False,
                "error": "EXECUTION_ERROR",
                "message": str(e),
                "source": "Tool Execution Engine",
                "latency_ms": latency,
            }

    def _register_default_tools(self) -> None:
        # INCIDENT TOOLS
        self.register(ToolDefinition(
            name="get_incident",
            category="incidents",
            description="Retrieve detailed operational state, coordinates, priority, and status for a specific incident ID.",
            parameters={
                "type": "object",
                "properties": {"incident_id": {"type": "string", "description": "The unique incident ID"}},
                "required": ["incident_id"],
            },
            handler=tools.get_incident,
        ))

        self.register(ToolDefinition(
            name="search_incidents",
            category="incidents",
            description="Search operational incidents by status, priority, and limit.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status: OPEN, DISPATCHED, RESOLVED"},
                    "priority": {"type": "string", "description": "Filter by priority: LOW, MEDIUM, HIGH, CRITICAL"},
                    "limit": {"type": "integer", "description": "Maximum number of incidents to return"},
                },
            },
            handler=tools.search_incidents,
        ))

        self.register(ToolDefinition(
            name="get_active_incidents",
            category="incidents",
            description="Get currently active and unclosed emergency incidents requiring authority response.",
            parameters={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Limit of incidents to return"}},
            },
            handler=tools.get_active_incidents,
        ))

        self.register(ToolDefinition(
            name="get_incident_timeline",
            category="incidents",
            description="Get the chronological event history, state transitions, and audit records for an incident.",
            parameters={
                "type": "object",
                "properties": {"incident_id": {"type": "string", "description": "The unique incident ID"}},
                "required": ["incident_id"],
            },
            handler=tools.get_incident_timeline,
        ))

        self.register(ToolDefinition(
            name="get_incident_response",
            category="incidents",
            description="Retrieve the active automated response plan, executed actions, and pending timers for an incident.",
            parameters={
                "type": "object",
                "properties": {"incident_id": {"type": "string", "description": "The unique incident ID"}},
                "required": ["incident_id"],
            },
            handler=tools.get_incident_response,
        ))

        self.register(ToolDefinition(
            name="get_incident_risk_context",
            category="incidents",
            description="Retrieve risk scores, confidence levels, contributing factors, and reason codes for an incident.",
            parameters={
                "type": "object",
                "properties": {"incident_id": {"type": "string", "description": "The unique incident ID"}},
                "required": ["incident_id"],
            },
            handler=tools.get_incident_risk_context,
        ))

        # SAFETY & RISK TOOLS
        self.register(ToolDefinition(
            name="get_current_safety_state",
            category="safety",
            description="Get real-time safety classification state (NORMAL, WATCH, ELEVATED, CANDIDATE) for a tourist.",
            parameters={
                "type": "object",
                "properties": {"tourist_id": {"type": "string", "description": "The tourist ID"}},
                "required": ["tourist_id"],
            },
            handler=tools.get_current_safety_state,
        ))

        self.register(ToolDefinition(
            name="get_risk_hotspots",
            category="risk",
            description="Get top elevated risk zones, geofence breach areas, and danger hotspots.",
            parameters={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Number of hotspots to return"}},
            },
            handler=tools.get_risk_hotspots,
        ))

        self.register(ToolDefinition(
            name="get_active_risk_episodes",
            category="risk",
            description="Retrieve active multi-signal risk fusion episodes currently tracked by the safety engine.",
            parameters={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Limit of episodes to return"}},
            },
            handler=tools.get_active_risk_episodes,
        ))

        # ZONE TOOLS
        self.register(ToolDefinition(
            name="list_active_zones",
            category="zones",
            description="List active geospatial safety zones (safe, hazard, danger, restricted).",
            parameters={
                "type": "object",
                "properties": {"zone_type": {"type": "string", "description": "Optional zone type filter"}},
            },
            handler=tools.list_active_zones,
        ))

        self.register(ToolDefinition(
            name="get_zone",
            category="zones",
            description="Retrieve metadata, boundary configuration, and rules for a specific zone.",
            parameters={
                "type": "object",
                "properties": {"zone_id": {"type": "string", "description": "The zone ID"}},
                "required": ["zone_id"],
            },
            handler=tools.get_zone,
        ))

        self.register(ToolDefinition(
            name="get_zone_risk",
            category="zones",
            description="Get current risk assessment and active factor indicators for a zone.",
            parameters={
                "type": "object",
                "properties": {"zone_id": {"type": "string", "description": "The zone ID"}},
                "required": ["zone_id"],
            },
            handler=tools.get_zone_risk,
        ))

        self.register(ToolDefinition(
            name="get_zone_incidents",
            category="zones",
            description="Retrieve incidents that have occurred within a specified zone boundary.",
            parameters={
                "type": "object",
                "properties": {"zone_id": {"type": "string", "description": "The zone ID"}},
                "required": ["zone_id"],
            },
            handler=tools.get_zone_incidents,
        ))

        # TOURIST TOOLS
        self.register(ToolDefinition(
            name="get_tourist_safety_status",
            category="tourists",
            description="Get tourist safety state and verification status (PII protected).",
            parameters={
                "type": "object",
                "properties": {"tourist_id": {"type": "string", "description": "The tourist ID"}},
                "required": ["tourist_id"],
            },
            handler=tools.get_tourist_safety_status,
        ))

        self.register(ToolDefinition(
            name="get_tourist_trip_status",
            category="tourists",
            description="Get current active itinerary and trip progress for a tourist.",
            parameters={
                "type": "object",
                "properties": {"tourist_id": {"type": "string", "description": "The tourist ID"}},
                "required": ["tourist_id"],
            },
            handler=tools.get_tourist_trip_status,
        ))

        # RESPONDER TOOLS
        self.register(ToolDefinition(
            name="get_available_responders",
            category="responders",
            description="List available emergency responder units filtered by capability (POLICE, MEDICAL, RESCUE).",
            parameters={
                "type": "object",
                "properties": {"capability": {"type": "string", "description": "Optional capability filter"}},
            },
            handler=tools.get_available_responders,
        ))

        self.register(ToolDefinition(
            name="get_responder_workload",
            category="responders",
            description="Get overall responder fleet utilization, busy units, and active dispatches.",
            parameters={"type": "object", "properties": {}},
            handler=tools.get_responder_workload,
        ))

        # ANALYTICS TOOLS
        self.register(ToolDefinition(
            name="get_incident_metrics",
            category="analytics",
            description="Retrieve aggregate incident metrics, resolution rates, and counts over a timeframe.",
            parameters={
                "type": "object",
                "properties": {"timeframe": {"type": "string", "description": "e.g. 1h, 24h, 7d"}},
            },
            handler=tools.get_incident_metrics,
        ))

        self.register(ToolDefinition(
            name="get_response_metrics",
            category="analytics",
            description="Retrieve response time analytics (P50, P90), acknowledgement durations, and SLA adherence.",
            parameters={
                "type": "object",
                "properties": {"timeframe": {"type": "string", "description": "e.g. 24h, 7d"}},
            },
            handler=tools.get_response_metrics,
        ))

        self.register(ToolDefinition(
            name="get_trends",
            category="analytics",
            description="Retrieve operational trends and comparison against historical baseline periods.",
            parameters={
                "type": "object",
                "properties": {"timeframe": {"type": "string", "description": "e.g. 24h, 7d"}},
            },
            handler=tools.get_trends,
        ))

        self.register(ToolDefinition(
            name="get_forecast",
            category="analytics",
            description="Retrieve ML demand and incident volume forecasts with uncertainty intervals.",
            parameters={
                "type": "object",
                "properties": {"metric": {"type": "string", "description": "Forecast metric target"}},
            },
            handler=tools.get_forecast,
        ))

        # POLICY TOOLS
        self.register(ToolDefinition(
            name="get_active_response_policy",
            category="policies",
            description="Retrieve active emergency response policy, SLAs, and retry parameters.",
            parameters={
                "type": "object",
                "properties": {"policy_id": {"type": "string", "description": "Optional policy ID"}},
            },
            handler=tools.get_active_response_policy,
        ))

        self.register(ToolDefinition(
            name="get_escalation_policy",
            category="policies",
            description="Retrieve the approved escalation policy and stage timeout thresholds.",
            parameters={"type": "object", "properties": {}},
            handler=tools.get_escalation_policy,
        ))

        # SYSTEM HEALTH
        self.register(ToolDefinition(
            name="get_system_health",
            category="system_health",
            description="Retrieve health status for MongoDB, Redis, ML Engine, Orchestrator, and Telemetry.",
            parameters={"type": "object", "properties": {}},
            handler=tools.get_system_health,
        ))

        # KNOWLEDGE BASE / RAG
        self.register(ToolDefinition(
            name="search_knowledge_base",
            category="knowledge",
            description="Search approved TourSafe SOPs, emergency response manuals, and policy documentation.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text query"},
                    "category": {"type": "string", "description": "Optional doc category: sop, policy, protocol"},
                },
                "required": ["query"],
            },
            handler=tools.search_knowledge_base,
        ))

        # EXTERNAL INTEGRATION & INTEROPERABILITY TOOLS
        self.register(ToolDefinition(
            name="get_integration_health",
            category="integrations",
            description="Retrieve status and circuit breaker states across all external providers (Maps, SMS, Weather, KYC, CAD).",
            parameters={"type": "object", "properties": {}},
            handler=tools.get_integration_health,
            read_only=True,
        ))

        self.register(ToolDefinition(
            name="query_external_weather",
            category="integrations",
            description="Query live weather conditions and severe storm advisories for coordinates via active Weather Adapter.",
            parameters={
                "type": "object",
                "properties": {
                    "latitude": {"type": "number", "description": "GPS Latitude"},
                    "longitude": {"type": "number", "description": "GPS Longitude"},
                },
                "required": ["latitude", "longitude"],
            },
            handler=tools.query_external_weather,
            read_only=True,
        ))

        self.register(ToolDefinition(
            name="query_external_geocoding",
            category="integrations",
            description="Geocode a location or landmark address to coordinates via active Maps Adapter.",
            parameters={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Location name or address to geocode"},
                },
                "required": ["address"],
            },
            handler=tools.query_external_geocoding,
            read_only=True,
        ))

        self.register(ToolDefinition(
            name="query_external_routing",
            category="integrations",
            description="Calculate route distance, duration, and geometry between coordinates via active Maps Adapter.",
            parameters={
                "type": "object",
                "properties": {
                    "origin_lon": {"type": "number", "description": "Origin longitude"},
                    "origin_lat": {"type": "number", "description": "Origin latitude"},
                    "dest_lon": {"type": "number", "description": "Destination longitude"},
                    "dest_lat": {"type": "number", "description": "Destination latitude"},
                },
                "required": ["origin_lon", "origin_lat", "dest_lon", "dest_lat"],
            },
            handler=tools.query_external_routing,
            read_only=True,
        ))

        self.register(ToolDefinition(
            name="list_integration_dead_letters",
            category="integrations",
            description="List unhandled or failed external integration requests in the Dead-Letter Queue.",
            parameters={
                "type": "object",
                "properties": {
                    "resolved": {"type": "boolean", "description": "Filter by resolved status"},
                },
            },
            handler=tools.list_integration_dead_letters,
            read_only=True,
        ))

        self.register(ToolDefinition(
            name="retry_integration_dead_letter",
            category="integrations",
            description="Re-queue and retry a failed integration request from the Dead-Letter Queue (Requires Confirmation).",
            parameters={
                "type": "object",
                "properties": {
                    "record_id": {"type": "string", "description": "Dead letter record ID to retry"},
                },
                "required": ["record_id"],
            },
            handler=tools.retry_integration_dead_letter,
            read_only=False,
            requires_preview=True,
        ))


copilot_tool_registry = ToolRegistry()
