# Architectural Decisions: Prompt 22 — Dispatch, Communication & Multi-Party Incident Coordination

## 1. Monotonic Server-Assigned Sequence Numbers over Timestamps

- **Decision**: Use MongoDB atomic `$inc: {"sequence_counter": 1}` to allocate strictly monotonic integer sequence numbers per incident channel.
- **Rationale**: Device clocks on mobile phones drift or may be intentionally misconfigured. Relying on client or server timestamps for message ordering leads to race conditions, out-of-order rendering, and inability to detect missing packets.
- **Alternatives Considered**:
  - *Client timestamps*: High clock skew risk.
  - *Snowflake IDs*: 64-bit integer IDs do not provide continuous gap detection (e.g. knowing whether a message between ID A and B was dropped).

---

## 2. Distinction Between Read Receipts and Critical Acknowledgements

- **Decision**: Implement `read_by` (map of `user_id -> ISO_TIMESTAMP`) separately from `acknowledged_by` (array of `MessageAcknowledgementRecord` with actor metadata and optional tactical notes).
- **Rationale**: In emergency response, knowing a tourist's screen rendered an instruction ("EVACUATE IMMEDIATELY") is insufficient. Command staff need unambiguous proof that the human acknowledged and understood the directive.
- **Alternatives Considered**:
  - *Single read status flag*: Inadequate for life-critical accountability.

---

## 3. Client Idempotency via `client_message_id`

- **Decision**: Index `{"incident_id": 1, "client_message_id": 1}` and verify existence prior to allocating a new server sequence.
- **Rationale**: Mobile network drops often cause requests to succeed on the server while failing to return a 200 response to the client. Idempotency guarantees safe client retries without double posting.
- **Alternatives Considered**:
  - *Deduplication on message content*: Prevents users from legitimately sending the same short message (e.g., "Yes", "Help") more than once.

---

## 4. Participant Restriction on Operational Handover

- **Decision**: When a responder initiates a handover, set their channel status to `RESTRICTED` rather than immediately removing them.
- **Rationale**: The outgoing responder needs ongoing read-only visibility into incident developments for tactical continuity, but must be prevented from issuing conflicting commands while awaiting replacement.
