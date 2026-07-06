"""
claude_agent.py
------------------------------------------------------------------
The AI layer on top of the deterministic auditor.

Kaevon's post asks how we build with Claude: we lead with Claude as
the architect and reasoning layer, and keep the money math in plain,
tested Python. Claude reads the messy carrier PDF, normalizes it into
structured lines, and drafts the human-quality dispute. It never
invents the numbers; it calls audit_invoice() via function calling and
reports exactly what the engine returns.

This is a working sketch of that wiring against the Anthropic SDK.
Set ANTHROPIC_API_KEY to run it live; the tools and control flow are
production-shaped, not pseudocode.
"""
from __future__ import annotations
import json
from typing import Any, Dict

from auditor import Invoice, InvoiceLine, audit_invoice, draft_dispute

# Tool schema Claude can call. Claude parses the PDF into these fields,
# then we run the deterministic audit and hand the result back.
AUDIT_TOOL = {
    "name": "audit_invoice",
    "description": "Audit a parsed LTL carrier invoice against the quoted rate and BOL. "
                   "Returns every overcharged line and the recoverable dollar amount.",
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_id": {"type": "string"},
            "carrier": {"type": "string"},
            "bol": {"type": "string"},
            "destination": {"type": "string"},
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "kind": {"type": "string", "enum": ["linehaul", "weight", "fsc", "accessorial"]},
                        "quoted": {"type": "number"},
                        "billed": {"type": "number"},
                        "rate": {"type": "number"},
                        "base": {"type": "number"},
                    },
                    "required": ["name", "kind", "quoted", "billed"],
                },
            },
        },
        "required": ["invoice_id", "carrier", "bol", "destination", "lines"],
    },
}

SYSTEM = (
    "You audit LTL freight invoices for Bells of Steel. Read the carrier invoice "
    "and the attached BOL, normalize the charges into structured lines, then call "
    "audit_invoice. Never estimate the recoverable amount yourself; report exactly "
    "what the tool returns, then write a firm, polite dispute email citing only the "
    "flagged lines."
)


def _run_audit_tool(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    inv = Invoice(
        invoice_id=tool_input["invoice_id"],
        carrier=tool_input["carrier"],
        bol=tool_input["bol"],
        destination=tool_input["destination"],
        lines=[InvoiceLine(**ln) for ln in tool_input["lines"]],
    )
    result = audit_invoice(inv)
    return {
        "invoice_id": result.invoice_id,
        "total_billed": result.total_billed,
        "total_overcharge": result.total_overcharge,
        "findings": [f.__dict__ for f in result.findings],
        "fallback_dispute": draft_dispute(inv, result),
    }


def review_invoice(carrier_pdf_text: str, bol_json: str) -> str:
    """
    Hand Claude the raw carrier PDF text and the BOL; it parses, calls the
    auditor via function calling, and returns the drafted dispute.
    """
    from anthropic import Anthropic  # pip install anthropic

    client = Anthropic()
    messages = [{
        "role": "user",
        "content": f"Carrier invoice:\n{carrier_pdf_text}\n\nBOL (quoted):\n{bol_json}",
    }]

    while True:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=SYSTEM,
            tools=[AUDIT_TOOL],
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use" and block.name == "audit_invoice":
                out = _run_audit_tool(block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out),
                })
        messages.append({"role": "user", "content": tool_results})
