"""Tools used by the IT Support agent — a mock ITSM/ticketing connector and
a system-status check, standing in for real Logic Apps/Power Automate
flows against ServiceNow/Jira in production."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from core.data.sql_store import SqlStore, Ticket
from core.tools.base import Tool

_SYSTEM_STATUS = {
    "vpn": "operational",
    "email": "operational",
    "identity-portal": "degraded (elevated latency in EU region)",
    "crm": "operational",
}


class CreateTicketTool(Tool):
    name = "create_support_ticket"
    description = "File a new IT support ticket on behalf of the user."
    parameters = {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["subject", "description"],
    }

    def __init__(self, sql: SqlStore) -> None:
        self._sql = sql

    async def run(self, subject: str, description: str, user_id: str = "anonymous", **_: Any) -> str:
        ticket_id = f"IT-{uuid.uuid4().hex[:6].upper()}"
        async with self._sql.session_factory() as session:
            session.add(Ticket(id=ticket_id, user_id=user_id, subject=subject, description=description))
            await session.commit()
        return f"Created ticket {ticket_id} (status: open)."


class CheckSystemStatusTool(Tool):
    name = "check_system_status"
    description = "Check the operational status of an internal system (vpn, email, identity-portal, crm)."
    parameters = {
        "type": "object",
        "properties": {"system": {"type": "string"}},
        "required": ["system"],
    }

    async def run(self, system: str, **_: Any) -> str:
        status = _SYSTEM_STATUS.get(system.lower())
        return f"{system}: {status}" if status else f"Unknown system '{system}'."


class LookupTicketTool(Tool):
    name = "lookup_ticket"
    description = "Look up an existing IT support ticket by id."
    parameters = {
        "type": "object",
        "properties": {"ticket_id": {"type": "string"}},
        "required": ["ticket_id"],
    }

    def __init__(self, sql: SqlStore) -> None:
        self._sql = sql

    async def run(self, ticket_id: str, **_: Any) -> str:
        async with self._sql.session_factory() as session:
            ticket = await session.scalar(select(Ticket).where(Ticket.id == ticket_id))
        if not ticket:
            return f"No ticket found with id {ticket_id}."
        return f"{ticket.id}: '{ticket.subject}' — status: {ticket.status}"
