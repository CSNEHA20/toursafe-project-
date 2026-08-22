"""
TourSafe Response Policy Engine & Policy Versioning Service

Manages configurable response policies, versioning, validation, safe simulations,
approval workflows, atomic rollbacks, and immutable audit logs.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()


from ...schemas.emergency import (
    ActionType,
    EscalationStageConfig,
    IncidentSeverity,
    NotificationChannel,
    PolicyCreateRequest,
    PolicySimulationRequest,
    PolicySimulationResult,
    PolicyStatus,
    PolicyTriggerType,
    PolicyUpdateRequest,
    ResponseActionConfig,
    ResponsePolicy,
)

logger = logging.getLogger("toursafe.emergency.response_policy")


class ResponsePolicyService:
    """
    Central service for managing emergency response policies and validation.
    """

    def __init__(self):
        self._cache: Dict[str, ResponsePolicy] = {}

    def get_default_policies(self) -> List[ResponsePolicy]:
        """
        Returns hardcoded production-grade default policies that seed MongoDB on startup.
        """
        sos_policy = ResponsePolicy(
            policy_id="pol_sos_emergency_v1",
            version="v1.0.0",
            name="Emergency SOS Fast-Track Policy",
            description="Authoritative response policy for manual tourist SOS emergencies with prioritized dispatch.",
            trigger_type=PolicyTriggerType.MANUAL_SOS,
            status=PolicyStatus.ACTIVE,
            created_at="2026-08-20T00:00:00+00:00",
            created_by="system_admin",
            approved_by="director_operations",
            approved_at="2026-08-20T00:00:00+00:00",
            initial_stage="DISPATCH",
            maximum_escalation_level=4,
            cooldown_seconds=45,
            ack_timeout_seconds=60,
            dispatch_timeout_seconds=180,
            max_retry_attempts=3,
            retry_backoff_seconds=10,
            human_override_required=False,
            emergency_contacts_enabled=True,
            target_sla_seconds=300,
            safety_guidance_text="SOS received. Emergency operations dispatched. Please remain in place if safe to do so.",
            initial_actions=[
                ResponseActionConfig(
                    action_key="act_sos_notify_authority",
                    type=ActionType.NOTIFY_AUTHORITY,
                    target="authority",
                    target_roles=["authority", "lead_operator", "command_center"],
                    channels=[NotificationChannel.PUSH, NotificationChannel.EMAIL],
                    parameters={"priority": "CRITICAL", "sound": "emergency_alarm"},
                    is_critical=True,
                    timeout_seconds=30,
                ),
                ResponseActionConfig(
                    action_key="act_sos_notify_tourist",
                    type=ActionType.NOTIFY_TOURIST,
                    target="tourist",
                    channels=[NotificationChannel.PUSH, NotificationChannel.SMS],
                    parameters={"guidance": "Help is on the way. Keep phone active."},
                    is_critical=False,
                    timeout_seconds=30,
                ),
                ResponseActionConfig(
                    action_key="act_sos_dispatch_primary",
                    type=ActionType.DISPATCH_RESPONDER,
                    target="responder",
                    required_capabilities=["FIRST_AID", "SECURITY"],
                    parameters={"auto_assign": True, "assignment_role": "PRIMARY"},
                    is_critical=True,
                    timeout_seconds=60,
                ),
                ResponseActionConfig(
                    action_key="act_sos_request_ack",
                    type=ActionType.REQUEST_ACKNOWLEDGEMENT,
                    target="responder",
                    depends_on=["act_sos_dispatch_primary"],
                    timeout_seconds=60,
                    is_critical=True,
                ),
            ],
            stages=[
                EscalationStageConfig(
                    stage=1,
                    name="Level 1: Unacknowledged SOS Timeout",
                    trigger="ACK_TIMEOUT",
                    delay_seconds=60,
                    escalate_severity_to=IncidentSeverity.CRITICAL,
                    notify_roles=["authority", "dispatch_supervisor"],
                    channels=[NotificationChannel.PUSH, NotificationChannel.SMS],
                    description="Primary responder failed to acknowledge SOS within 60 seconds.",
                    actions=[
                        ResponseActionConfig(
                            action_key="act_stage1_redispatch",
                            type=ActionType.DISPATCH_RESPONDER,
                            target="responder",
                            required_capabilities=["FIRST_AID", "SECURITY"],
                            parameters={"auto_assign": True, "assignment_role": "PRIMARY", "retry_count": 1},
                            is_critical=True,
                            timeout_seconds=60,
                        ),
                    ],
                ),
                EscalationStageConfig(
                    stage=2,
                    name="Level 2: Supervisor & Multi-Unit Escalation",
                    trigger="STAGE1_TIMEOUT",
                    delay_seconds=120,
                    escalate_severity_to=IncidentSeverity.CRITICAL,
                    notify_roles=["authority_supervisor", "district_commander"],
                    channels=[NotificationChannel.PUSH, NotificationChannel.SMS, NotificationChannel.VOICE],
                    description="Second responder failed or unacknowledged. Notifying field supervisors and adding secondary unit.",
                    actions=[
                        ResponseActionConfig(
                            action_key="act_stage2_supervisor",
                            type=ActionType.REQUEST_SUPERVISOR,
                            target="supervisor",
                            parameters={"alert_level": "RED"},
                            is_critical=True,
                        ),
                        ResponseActionConfig(
                            action_key="act_stage2_secondary_unit",
                            type=ActionType.DISPATCH_RESPONDER,
                            target="responder",
                            required_capabilities=["SECURITY", "RESCUE"],
                            parameters={"auto_assign": True, "assignment_role": "SECONDARY"},
                            is_critical=False,
                        ),
                    ],
                ),
                EscalationStageConfig(
                    stage=3,
                    name="Level 3: Regional Command Escalation",
                    trigger="SLA_BREACH",
                    delay_seconds=240,
                    escalate_severity_to=IncidentSeverity.CRITICAL,
                    notify_roles=["regional_director", "emergency_coordinator"],
                    channels=[NotificationChannel.PUSH, NotificationChannel.SMS, NotificationChannel.VOICE],
                    description="Response exceeding SLA threshold. Full incident command activation.",
                    actions=[
                        ResponseActionConfig(
                            action_key="act_stage3_regional_escalate",
                            type=ActionType.ESCALATE,
                            target="command_center",
                            parameters={"level": "REGIONAL_COMMAND"},
                            is_critical=True,
                        ),
                    ],
                ),
            ],
        )

        fusion_policy = ResponsePolicy(
            policy_id="pol_safety_fusion_v1",
            version="v1.0.0",
            name="Safety Engine Anomaly & Fusion Policy",
            description="Policy triggered by automated safety state machine (Elevated/Incident Candidate).",
            trigger_type=PolicyTriggerType.SAFETY_STATE,
            status=PolicyStatus.ACTIVE,
            created_at="2026-08-20T00:00:00+00:00",
            created_by="system_admin",
            approved_by="director_operations",
            approved_at="2026-08-20T00:00:00+00:00",
            initial_stage="NOTIFY",
            maximum_escalation_level=4,
            cooldown_seconds=60,
            ack_timeout_seconds=120,
            dispatch_timeout_seconds=300,
            max_retry_attempts=3,
            retry_backoff_seconds=15,
            human_override_required=False,
            emergency_contacts_enabled=True,
            target_sla_seconds=600,
            safety_guidance_text="Unusual activity detected. Operations center alerted for safety verification.",
            initial_actions=[
                ResponseActionConfig(
                    action_key="act_fusion_notify_authority",
                    type=ActionType.NOTIFY_AUTHORITY,
                    target="authority",
                    target_roles=["authority", "lead_operator"],
                    channels=[NotificationChannel.PUSH, NotificationChannel.EMAIL],
                    parameters={"priority": "HIGH"},
                    is_critical=True,
                    timeout_seconds=45,
                ),
                ResponseActionConfig(
                    action_key="act_fusion_notify_tourist",
                    type=ActionType.NOTIFY_TOURIST,
                    target="tourist",
                    channels=[NotificationChannel.PUSH],
                    parameters={"guidance": "Please confirm your safety status via the app prompt."},
                    is_critical=False,
                    timeout_seconds=45,
                ),
                ResponseActionConfig(
                    action_key="act_fusion_dispatch_primary",
                    type=ActionType.DISPATCH_RESPONDER,
                    target="responder",
                    required_capabilities=["SECURITY", "FIRST_AID"],
                    parameters={"auto_assign": True, "assignment_role": "PRIMARY"},
                    is_critical=True,
                    timeout_seconds=120,
                ),
                ResponseActionConfig(
                    action_key="act_fusion_request_ack",
                    type=ActionType.REQUEST_ACKNOWLEDGEMENT,
                    target="responder",
                    depends_on=["act_fusion_dispatch_primary"],
                    timeout_seconds=120,
                    is_critical=True,
                ),
            ],
            stages=[
                EscalationStageConfig(
                    stage=1,
                    name="Level 1: Unacknowledged Incident Timeout",
                    trigger="ACK_TIMEOUT",
                    delay_seconds=120,
                    escalate_severity_to=IncidentSeverity.HIGH,
                    notify_roles=["authority", "dispatch_lead"],
                    channels=[NotificationChannel.PUSH, NotificationChannel.EMAIL],
                    description="Responder did not acknowledge within 120s window.",
                    actions=[
                        ResponseActionConfig(
                            action_key="act_stage1_redispatch",
                            type=ActionType.DISPATCH_RESPONDER,
                            target="responder",
                            required_capabilities=["SECURITY"],
                            parameters={"auto_assign": True, "assignment_role": "PRIMARY"},
                            is_critical=True,
                            timeout_seconds=90,
                        ),
                    ],
                ),
                EscalationStageConfig(
                    stage=2,
                    name="Level 2: Supervisor Escalation",
                    trigger="STAGE1_TIMEOUT",
                    delay_seconds=240,
                    escalate_severity_to=IncidentSeverity.CRITICAL,
                    notify_roles=["authority_supervisor"],
                    channels=[NotificationChannel.PUSH, NotificationChannel.SMS],
                    description="Unassigned or unacknowledged anomaly past 240s.",
                    actions=[
                        ResponseActionConfig(
                            action_key="act_stage2_supervisor",
                            type=ActionType.REQUEST_SUPERVISOR,
                            target="supervisor",
                            parameters={"alert_level": "YELLOW"},
                            is_critical=True,
                        ),
                    ],
                ),
            ],
        )

        geofence_policy = ResponsePolicy(
            policy_id="pol_geofence_hazard_v1",
            version="v1.0.0",
            name="Hazardous Geofence Zone Breach Policy",
            description="Triggered when tourist dwells in high-risk or restricted geospatial zone.",
            trigger_type=PolicyTriggerType.SAFETY_STATE,
            status=PolicyStatus.ACTIVE,
            created_at="2026-08-20T00:00:00+00:00",
            created_by="system_admin",
            approved_by="director_operations",
            approved_at="2026-08-20T00:00:00+00:00",
            initial_stage="NOTIFY",
            maximum_escalation_level=3,
            cooldown_seconds=60,
            ack_timeout_seconds=90,
            dispatch_timeout_seconds=240,
            max_retry_attempts=3,
            retry_backoff_seconds=15,
            target_sla_seconds=450,
            safety_guidance_text="You have entered a restricted or hazard zone. Please follow safe navigation routes immediately.",
            initial_actions=[
                ResponseActionConfig(
                    action_key="act_geo_notify_authority",
                    type=ActionType.NOTIFY_AUTHORITY,
                    target="authority",
                    target_roles=["authority", "park_ranger"],
                    channels=[NotificationChannel.PUSH],
                    is_critical=True,
                    timeout_seconds=45,
                ),
                ResponseActionConfig(
                    action_key="act_geo_notify_tourist",
                    type=ActionType.NOTIFY_TOURIST,
                    target="tourist",
                    channels=[NotificationChannel.PUSH, NotificationChannel.SMS],
                    is_critical=False,
                    timeout_seconds=45,
                ),
                ResponseActionConfig(
                    action_key="act_geo_dispatch",
                    type=ActionType.DISPATCH_RESPONDER,
                    target="responder",
                    required_capabilities=["SECURITY", "SEARCH"],
                    parameters={"auto_assign": True},
                    is_critical=True,
                    timeout_seconds=90,
                ),
            ],
            stages=[
                EscalationStageConfig(
                    stage=1,
                    name="Level 1: Zone Breach Unassigned",
                    trigger="ACK_TIMEOUT",
                    delay_seconds=90,
                    escalate_severity_to=IncidentSeverity.HIGH,
                    notify_roles=["authority_supervisor"],
                    channels=[NotificationChannel.PUSH, NotificationChannel.EMAIL],
                    description="No ranger acknowledged zone breach dispatch.",
                    actions=[],
                ),
            ],
        )

        return [sos_policy, fusion_policy, geofence_policy]

    async def init_default_policies(self):
        """
        Seeds default approved & active policies into MongoDB if not present.
        """
        db = get_database()
        for policy in self.get_default_policies():
            existing = await db.response_policies.find_one({"policy_id": policy.policy_id})
            if not existing:
                await db.response_policies.insert_one(policy.model_dump())
                logger.info("Seeded default response policy: %s (%s)", policy.name, policy.policy_id)

    def validate_policy(self, policy: ResponsePolicy) -> Tuple[bool, List[str]]:
        """
        Strictly validates a response policy against structural and operational integrity rules.
        Rejects:
        - Invalid or negative timeouts
        - Undefined actions or missing targets
        - Circular escalation stage sequences
        - Missing initial actions
        - Maximum escalation level lower than defined stages count
        """
        errors = []

        if policy.ack_timeout_seconds <= 0 or policy.ack_timeout_seconds > 86400:
            errors.append(f"Invalid ack_timeout_seconds: {policy.ack_timeout_seconds}. Must be between 1 and 86400.")
        if policy.dispatch_timeout_seconds <= 0 or policy.dispatch_timeout_seconds > 86400:
            errors.append(f"Invalid dispatch_timeout_seconds: {policy.dispatch_timeout_seconds}. Must be between 1 and 86400.")
        if policy.target_sla_seconds <= 0:
            errors.append(f"Invalid target_sla_seconds: {policy.target_sla_seconds}. Must be > 0.")
        if policy.maximum_escalation_level < len(policy.stages):
            errors.append(f"maximum_escalation_level ({policy.maximum_escalation_level}) cannot be less than defined stages count ({len(policy.stages)}).")

        # Validate initial actions
        if not policy.initial_actions:
            errors.append("Policy must define at least one initial response action.")

        action_keys = set()
        for act in policy.initial_actions:
            if not act.action_key:
                errors.append("Each action must have a non-empty action_key.")
            if act.action_key in action_keys:
                errors.append(f"Duplicate action_key '{act.action_key}' in initial actions.")
            action_keys.add(act.action_key)

            if act.timeout_seconds <= 0:
                errors.append(f"Action '{act.action_key}' has invalid timeout_seconds <= 0.")
            if act.max_attempts <= 0 or act.max_attempts > 10:
                errors.append(f"Action '{act.action_key}' max_attempts must be between 1 and 10.")
            if not act.target:
                errors.append(f"Action '{act.action_key}' must have a valid target.")

            # Validate dependencies
            for dep in act.depends_on:
                if dep == act.action_key:
                    errors.append(f"Action '{act.action_key}' cannot depend on itself.")

        # Validate stages and check circular escalations
        seen_stages = set()
        last_stage = 0
        for stage in policy.stages:
            if stage.stage <= 0:
                errors.append(f"Stage number must be >= 1, found {stage.stage}.")
            if stage.stage in seen_stages:
                errors.append(f"Duplicate stage number {stage.stage} found in escalation stages.")
            seen_stages.add(stage.stage)

            if stage.stage <= last_stage:
                errors.append(f"Escalation stages must be strictly monotonically increasing. Stage {stage.stage} follows {last_stage}.")
            last_stage = stage.stage

            if stage.delay_seconds <= 0:
                errors.append(f"Stage {stage.stage} must have delay_seconds > 0.")
            if not stage.notify_roles:
                errors.append(f"Stage {stage.stage} must specify at least one notify_role.")

            # Validate stage actions
            for s_act in stage.actions:
                if not s_act.action_key:
                    errors.append(f"Stage {stage.stage} action missing action_key.")
                if s_act.action_key in action_keys:
                    errors.append(f"Duplicate action_key '{s_act.action_key}' across policy.")
                action_keys.add(s_act.action_key)

        return (len(errors) == 0, errors)

    async def get_active_policy_for_trigger(self, trigger_type: PolicyTriggerType) -> Optional[ResponsePolicy]:
        """
        Retrieves the currently ACTIVE response policy for the given trigger type.
        """
        db = get_database()
        doc = await db.response_policies.find_one({
            "trigger_type": trigger_type.value if hasattr(trigger_type, "value") else str(trigger_type),
            "status": PolicyStatus.ACTIVE.value,
        })
        if doc:
            return ResponsePolicy(**doc)

        # Fallback to in-memory default
        for p in self.get_default_policies():
            if (p.trigger_type.value if hasattr(p.trigger_type, "value") else str(p.trigger_type)) == (trigger_type.value if hasattr(trigger_type, "value") else str(trigger_type)):
                return p

        return None

    async def get_policy_by_id(self, policy_id: str) -> Optional[ResponsePolicy]:
        """
        Retrieves a response policy by ID.
        """
        db = get_database()
        doc = await db.response_policies.find_one({"policy_id": policy_id})
        if doc:
            return ResponsePolicy(**doc)
        return None

    async def list_policies(
        self,
        trigger_type: Optional[PolicyTriggerType] = None,
        status: Optional[PolicyStatus] = None,
    ) -> List[ResponsePolicy]:
        """
        Lists response policies filtered by trigger type or status.
        """
        db = get_database()
        query: Dict[str, Any] = {}
        if trigger_type:
            query["trigger_type"] = trigger_type.value if hasattr(trigger_type, "value") else str(trigger_type)
        if status:
            query["status"] = status.value if hasattr(status, "value") else str(status)

        cursor = db.response_policies.find(query).sort("created_at", -1)
        policies = []
        async for doc in cursor:
            policies.append(ResponsePolicy(**doc))
        return policies

    async def create_policy(self, req: PolicyCreateRequest, user_id: str = "system") -> ResponsePolicy:
        """
        Creates a new draft response policy with validation and audit trail.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        policy = ResponsePolicy(
            policy_id=f"pol_{uuid.uuid4().hex[:10]}",
            version="v1.0.0",
            name=req.name,
            description=req.description or "",
            trigger_type=req.trigger_type,
            status=PolicyStatus.DRAFT,
            created_at=now_iso,
            created_by=user_id,
            initial_stage=req.initial_stage,
            stages=req.stages,
            initial_actions=req.initial_actions,
            maximum_escalation_level=req.maximum_escalation_level,
            cooldown_seconds=req.cooldown_seconds,
            ack_timeout_seconds=req.ack_timeout_seconds,
            dispatch_timeout_seconds=req.dispatch_timeout_seconds,
            max_retry_attempts=req.max_retry_attempts,
            retry_backoff_seconds=req.retry_backoff_seconds,
            human_override_required=req.human_override_required,
            emergency_contacts_enabled=req.emergency_contacts_enabled,
            target_sla_seconds=req.target_sla_seconds,
            safety_guidance_text=req.safety_guidance_text,
        )

        valid, errors = self.validate_policy(policy)
        if not valid:
            raise ValueError(f"Policy validation failed: {'; '.join(errors)}")

        db = get_database()
        await db.response_policies.insert_one(policy.model_dump())
        await self._audit_policy_change(policy.policy_id, "CREATED", user_id, "Policy created as DRAFT")
        return policy

    async def update_policy(self, policy_id: str, req: PolicyUpdateRequest, user_id: str = "system") -> ResponsePolicy:
        """
        Updates an existing draft or testing policy. Rejects modifications to ACTIVE policies (requires creating new version).
        """
        db = get_database()
        existing_doc = await db.response_policies.find_one({"policy_id": policy_id})
        if not existing_doc:
            raise ValueError(f"Policy '{policy_id}' not found.")

        existing = ResponsePolicy(**existing_doc)
        if existing.status == PolicyStatus.ACTIVE:
            raise ValueError("Active production policies cannot be directly mutated. Create a new policy version or clone to draft.")

        # Apply updates
        update_data = req.model_dump(exclude_unset=True)
        updated_dict = existing.model_dump()
        updated_dict.update(update_data)
        updated_policy = ResponsePolicy(**updated_dict)

        valid, errors = self.validate_policy(updated_policy)
        if not valid:
            raise ValueError(f"Policy validation failed: {'; '.join(errors)}")

        await db.response_policies.replace_one({"policy_id": policy_id}, updated_policy.model_dump())
        await self._audit_policy_change(policy_id, "UPDATED", user_id, f"Fields updated: {list(update_data.keys())}")
        return updated_policy

    async def approve_policy(self, policy_id: str, user_id: str, reason: str) -> ResponsePolicy:
        """
        Approves a DRAFT or TESTING policy, preparing it for production activation.
        """
        db = get_database()
        existing_doc = await db.response_policies.find_one({"policy_id": policy_id})
        if not existing_doc:
            raise ValueError(f"Policy '{policy_id}' not found.")

        existing = ResponsePolicy(**existing_doc)
        valid, errors = self.validate_policy(existing)
        if not valid:
            raise ValueError(f"Cannot approve invalid policy: {'; '.join(errors)}")

        now_iso = datetime.now(timezone.utc).isoformat()
        existing.status = PolicyStatus.APPROVED
        existing.approved_by = user_id
        existing.approved_at = now_iso

        await db.response_policies.replace_one({"policy_id": policy_id}, existing.model_dump())
        await self._audit_policy_change(policy_id, "APPROVED", user_id, f"Approved for production. Reason: {reason}")
        return existing

    async def activate_policy(self, policy_id: str, user_id: str) -> ResponsePolicy:
        """
        Activates an APPROVED policy. Automatically transitions the existing active policy for the same trigger to RETIRED.
        """
        db = get_database()
        existing_doc = await db.response_policies.find_one({"policy_id": policy_id})
        if not existing_doc:
            raise ValueError(f"Policy '{policy_id}' not found.")

        target_policy = ResponsePolicy(**existing_doc)
        if target_policy.status != PolicyStatus.APPROVED and target_policy.status != PolicyStatus.ACTIVE:
            raise ValueError(f"Only APPROVED policies can be activated. Current status is {target_policy.status.value}.")

        # Retire currently active policy for same trigger
        trig_val = target_policy.trigger_type.value if hasattr(target_policy.trigger_type, "value") else str(target_policy.trigger_type)
        await db.response_policies.update_many(
            {"trigger_type": trig_val, "status": PolicyStatus.ACTIVE.value, "policy_id": {"$ne": policy_id}},
            {"$set": {"status": PolicyStatus.RETIRED.value}},
        )

        target_policy.status = PolicyStatus.ACTIVE
        await db.response_policies.replace_one({"policy_id": policy_id}, target_policy.model_dump())
        await self._audit_policy_change(policy_id, "ACTIVATED", user_id, f"Policy activated for trigger {trig_val}")
        return target_policy

    async def rollback_policy(self, trigger_type: PolicyTriggerType, target_version: str, user_id: str, reason: str) -> ResponsePolicy:
        """
        Atomically rolls back the active policy for a trigger type to a previously approved or retired version.
        """
        db = get_database()
        trig_val = trigger_type.value if hasattr(trigger_type, "value") else str(trigger_type)
        candidate = await db.response_policies.find_one({
            "trigger_type": trig_val,
            "version": target_version,
            "status": {"$in": [PolicyStatus.APPROVED.value, PolicyStatus.RETIRED.value, PolicyStatus.ACTIVE.value]},
        })
        if not candidate:
            raise ValueError(f"No approved/retired policy found for trigger {trig_val} with version {target_version}")

        target_policy = ResponsePolicy(**candidate)

        # Retire current active
        await db.response_policies.update_many(
            {"trigger_type": trig_val, "status": PolicyStatus.ACTIVE.value},
            {"$set": {"status": PolicyStatus.RETIRED.value}},
        )

        target_policy.status = PolicyStatus.ACTIVE
        await db.response_policies.replace_one({"policy_id": target_policy.policy_id}, target_policy.model_dump())
        await self._audit_policy_change(
            target_policy.policy_id,
            "ROLLED_BACK",
            user_id,
            f"Rolled back to version {target_version}. Reason: {reason}",
        )
        return target_policy

    def simulate_policy(self, req: PolicySimulationRequest, target_policy: Optional[ResponsePolicy] = None) -> PolicySimulationResult:
        """
        Safe simulation sandbox.
        Evaluates what actions, stages, timeouts, and notifications WOULD occur given a sample incident or risk state
        WITHOUT side effects (no actual notifications sent, no responders dispatched, no incidents created).
        """
        policy = target_policy
        if not policy and req.custom_policy:
            policy = ResponsePolicy(
                policy_id="sim_custom",
                version="sim.v1",
                name=req.custom_policy.name,
                description=req.custom_policy.description or "",
                trigger_type=req.custom_policy.trigger_type,
                status=PolicyStatus.TESTING,
                initial_stage=req.custom_policy.initial_stage,
                stages=req.custom_policy.stages,
                initial_actions=req.custom_policy.initial_actions,
                maximum_escalation_level=req.custom_policy.maximum_escalation_level,
                cooldown_seconds=req.custom_policy.cooldown_seconds,
                ack_timeout_seconds=req.custom_policy.ack_timeout_seconds,
                dispatch_timeout_seconds=req.custom_policy.dispatch_timeout_seconds,
                max_retry_attempts=req.custom_policy.max_retry_attempts,
                retry_backoff_seconds=req.custom_policy.retry_backoff_seconds,
                target_sla_seconds=req.custom_policy.target_sla_seconds,
            )

        if not policy:
            for p in self.get_default_policies():
                if (p.trigger_type.value if hasattr(p.trigger_type, "value") else str(p.trigger_type)) == (req.mock_trigger_type.value if hasattr(req.mock_trigger_type, "value") else str(req.mock_trigger_type)):
                    policy = p
                    break

        if not policy:
            policy = self.get_default_policies()[0]

        valid, errors = self.validate_policy(policy)

        # Build simulated execution timeline
        simulated_timeline = []
        current_time_offset = 0

        # Stage 0: Initial Actions
        for act in policy.initial_actions:
            simulated_timeline.append({
                "time_offset_seconds": current_time_offset,
                "stage": 0,
                "action_key": act.action_key,
                "action_type": act.type.value if hasattr(act.type, "value") else str(act.type),
                "target": act.target,
                "is_critical": act.is_critical,
                "simulated_outcome": "SUCCESS" if (act.type != ActionType.DISPATCH_RESPONDER or req.mock_has_available_responder) else "NO_RESPONDER_AVAILABLE",
                "notes": f"Initial action triggered for {act.target}",
            })

        # Stage 1-N: Escalation projections if ack expires
        has_supervisor = False
        has_secondary_dispatch = False
        warnings = []

        if not req.mock_has_available_responder:
            warnings.append("No responder available for primary dispatch; immediate escalation recommended.")

        cumulative_delay = policy.ack_timeout_seconds
        for stage in policy.stages:
            simulated_timeline.append({
                "time_offset_seconds": cumulative_delay,
                "stage": stage.stage,
                "stage_name": stage.name,
                "trigger": stage.trigger,
                "target_severity": stage.escalate_severity_to.value if hasattr(stage.escalate_severity_to, "value") else str(stage.escalate_severity_to),
                "simulated_outcome": "STAGE_ESCALATED",
                "notify_roles": stage.notify_roles,
                "notes": stage.description,
            })

            for s_act in stage.actions:
                act_type_str = s_act.type.value if hasattr(s_act.type, "value") else str(s_act.type)
                if s_act.type == ActionType.REQUEST_SUPERVISOR:
                    has_supervisor = True
                if s_act.type == ActionType.DISPATCH_RESPONDER:
                    has_secondary_dispatch = True

                simulated_timeline.append({
                    "time_offset_seconds": cumulative_delay + 5,
                    "stage": stage.stage,
                    "action_key": s_act.action_key,
                    "action_type": act_type_str,
                    "target": s_act.target,
                    "simulated_outcome": "SUCCESS",
                    "notes": f"Stage {stage.stage} action executed",
                })

            cumulative_delay += stage.delay_seconds

        projected_stages = [
            {
                "stage": s.stage,
                "name": s.name,
                "delay_seconds": s.delay_seconds,
                "target_severity": s.escalate_severity_to.value if hasattr(s.escalate_severity_to, "value") else str(s.escalate_severity_to),
                "notify_roles": s.notify_roles,
                "actions_count": len(s.actions),
            }
            for s in policy.stages
        ]

        return PolicySimulationResult(
            policy_name=policy.name,
            policy_version=policy.version,
            valid=valid,
            validation_errors=errors,
            initial_actions_count=len(policy.initial_actions),
            projected_stages=projected_stages,
            simulated_timeline=simulated_timeline,
            estimated_resolution_time_seconds=min(cumulative_delay, policy.target_sla_seconds),
            has_supervisor_fallback=has_supervisor,
            has_secondary_dispatch=has_secondary_dispatch,
            is_safe=valid and (len(errors) == 0),
            warnings=warnings,
        )

    async def _audit_policy_change(self, policy_id: str, action: str, actor_id: str, details: str):
        """
        Writes immutable policy audit log into MongoDB.
        """
        db = get_database()
        audit_entry = {
            "audit_id": f"pau_{uuid.uuid4().hex[:12]}",
            "policy_id": policy_id,
            "action": action,
            "actor_id": actor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }
        await db.policy_audit_logs.insert_one(audit_entry)


response_policy_service = ResponsePolicyService()
