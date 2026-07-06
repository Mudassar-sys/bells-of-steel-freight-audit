"""
auditor.py
------------------------------------------------------------------
Freight invoice audit engine for Bells of Steel.

Heavy, oversized gym equipment ships LTL, where carriers routinely
overbill: reweighs above the BOL weight, fuel surcharges above the
agreed percentage, unauthorized accessorials (detention, residential,
reclassification), and linehaul billed above the quote.

This module is the deterministic core. It takes the quoted rate and
BOL (from EasyPost / Brightpearl) plus the parsed carrier invoice, and
returns every line that does not match, with the exact recoverable
amount. Claude sits on top of it (see claude_agent.py) to read messy
PDFs and draft the dispute; the money math stays here, testable and
repeatable, so a disputed dollar is a fact, not a guess.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Literal

LineKind = Literal["linehaul", "weight", "fsc", "accessorial"]

# tolerance before we flag a reweigh (carriers get small legitimate variance)
WEIGHT_TOLERANCE = 0.03


@dataclass
class InvoiceLine:
    name: str
    kind: LineKind
    quoted: float          # quoted rate/weight/pct/amount per the BOL
    billed: float          # what the carrier actually billed
    rate: float = 0.0      # $/lb for weight lines
    base: float = 0.0      # linehaul base for fsc lines


@dataclass
class Invoice:
    invoice_id: str
    carrier: str
    bol: str
    destination: str
    lines: List[InvoiceLine] = field(default_factory=list)


@dataclass
class Finding:
    name: str
    quoted_cost: float
    billed_cost: float
    overcharge: float
    reason: str


@dataclass
class AuditResult:
    invoice_id: str
    carrier: str
    total_billed: float
    total_overcharge: float
    findings: List[Finding]

    @property
    def is_clean(self) -> bool:
        return self.total_overcharge <= 0.0


def _line_cost(line: InvoiceLine, use: str) -> float:
    """Dollar cost of a line, for either 'quoted' or 'billed'."""
    value = getattr(line, use)
    if line.kind == "weight":
        return value * line.rate
    if line.kind == "fsc":
        return line.base * value
    return value


def audit_invoice(inv: Invoice) -> AuditResult:
    """Compare a carrier invoice line by line against the quote and BOL."""
    findings: List[Finding] = []
    total_billed = 0.0
    total_over = 0.0

    for line in inv.lines:
        q_cost = _line_cost(line, "quoted")
        b_cost = _line_cost(line, "billed")
        total_billed += b_cost
        over = round(b_cost - q_cost, 2)

        if line.kind == "weight":
            if line.billed > line.quoted * (1 + WEIGHT_TOLERANCE):
                findings.append(Finding(
                    line.name, q_cost, b_cost, over,
                    f"reweigh billed {line.billed:.0f} lb vs BOL {line.quoted:.0f} lb",
                ))
                total_over += over
        elif line.kind == "fsc":
            if line.billed > line.quoted + 1e-6:
                findings.append(Finding(
                    line.name, q_cost, b_cost, over,
                    f"fuel surcharge {line.billed*100:.0f}% vs agreed {line.quoted*100:.0f}%",
                ))
                total_over += over
        else:  # linehaul or accessorial
            if line.billed > line.quoted + 1e-6:
                label = "linehaul above quote" if line.kind == "linehaul" else "unauthorized accessorial"
                findings.append(Finding(
                    line.name, q_cost, b_cost, over, f"{label} (+${over:,.2f})",
                ))
                total_over += over

    return AuditResult(
        invoice_id=inv.invoice_id,
        carrier=inv.carrier,
        total_billed=round(total_billed, 2),
        total_overcharge=round(total_over, 2),
        findings=findings,
    )


def draft_dispute(inv: Invoice, result: AuditResult) -> str:
    """Deterministic fallback dispute (Claude produces the polished version)."""
    bullet = "\n".join(f"  - {f.name}: {f.reason} (+${f.overcharge:,.2f})" for f in result.findings)
    domain = "".join(c for c in inv.carrier.lower() if c.isalpha())
    return (
        f"To: disputes@{domain}.com\n"
        f"Subject: Billing dispute - Invoice {inv.invoice_id} / {inv.bol}\n\n"
        f"Hello,\n\n"
        f"On invoice {inv.invoice_id} ({inv.bol}, {inv.destination}) we identified "
        f"{len(result.findings)} charge(s) that do not match our agreed rate and BOL:\n\n"
        f"{bullet}\n\n"
        f"Total disputed amount: ${result.total_overcharge:,.2f}. BOL and rate "
        f"confirmation attached. Please issue a corrected invoice or credit.\n\n"
        f"Thanks,\nAccounts Payable, Bells of Steel"
    )


if __name__ == "__main__":
    demo = Invoice(
        invoice_id="DR-88142", carrier="Day & Ross", bol="BOL-77213", destination="Indianapolis, IN",
        lines=[
            InvoiceLine("Linehaul", "linehaul", 412.00, 412.00),
            InvoiceLine("Weight (reweigh)", "weight", 640, 815, rate=0.42),
            InvoiceLine("Fuel surcharge", "fsc", 0.31, 0.31, base=412.00),
            InvoiceLine("Residential delivery", "accessorial", 0, 0),
        ],
    )
    res = audit_invoice(demo)
    print(f"{res.invoice_id}: ${res.total_overcharge:,.2f} recoverable, {len(res.findings)} flagged")
    print(draft_dispute(demo, res))
