"""
test_auditor.py
------------------------------------------------------------------
Proof that a disputed dollar is a fact, not a guess. Run: pytest
"""
from auditor import Invoice, InvoiceLine, audit_invoice, draft_dispute


def _inv(lines):
    return Invoice("TEST-1", "Day & Ross", "BOL-1", "Indianapolis, IN", lines)


def test_reweigh_overcharge_is_caught():
    inv = _inv([
        InvoiceLine("Linehaul", "linehaul", 412.00, 412.00),
        InvoiceLine("Weight", "weight", 640, 815, rate=0.42),  # 175 lb over
    ])
    res = audit_invoice(inv)
    assert len(res.findings) == 1
    # 175 lb * $0.42 = $73.50
    assert res.total_overcharge == 73.50


def test_fuel_surcharge_above_agreed_is_caught():
    inv = _inv([
        InvoiceLine("Linehaul", "linehaul", 288.00, 288.00),
        InvoiceLine("Fuel surcharge", "fsc", 0.29, 0.34, base=288.00),
    ])
    res = audit_invoice(inv)
    # (0.34 - 0.29) * 288 = 14.40
    assert res.total_overcharge == 14.40


def test_unauthorized_accessorial_is_caught():
    inv = _inv([
        InvoiceLine("Linehaul", "linehaul", 288.00, 288.00),
        InvoiceLine("Detention", "accessorial", 0.0, 75.00),
    ])
    res = audit_invoice(inv)
    assert res.total_overcharge == 75.00
    assert "unauthorized" in res.findings[0].reason


def test_small_reweigh_within_tolerance_is_not_flagged():
    inv = _inv([
        InvoiceLine("Weight", "weight", 1000, 1020, rate=0.40),  # 2% over, under tolerance
    ])
    res = audit_invoice(inv)
    assert res.is_clean
    assert res.total_overcharge == 0.0


def test_clean_invoice_produces_no_findings():
    inv = _inv([
        InvoiceLine("Linehaul", "linehaul", 196.00, 196.00),
        InvoiceLine("Weight", "weight", 410, 410, rate=0.34),
        InvoiceLine("Fuel surcharge", "fsc", 0.28, 0.28, base=196.00),
    ])
    res = audit_invoice(inv)
    assert res.is_clean
    assert res.findings == []


def test_dispute_only_cites_flagged_lines():
    inv = _inv([
        InvoiceLine("Linehaul", "linehaul", 412.00, 412.00),
        InvoiceLine("Weight", "weight", 640, 815, rate=0.42),
        InvoiceLine("Residential delivery", "accessorial", 0.0, 38.00),
    ])
    res = audit_invoice(inv)
    text = draft_dispute(inv, res)
    assert "Weight" in text
    assert "Residential delivery" in text
    assert "Linehaul" not in text.split("do not match")[1]  # clean line not disputed
