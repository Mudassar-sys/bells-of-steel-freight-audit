# Bells of Steel - Freight Invoice Audit Copilot

An AI-first internal tool that recovers margin on heavy LTL freight. It matches every carrier invoice line against the quoted rate and BOL, flags overcharges, and drafts the dispute. Built end to end on your stack, the way you said you want to work: Claude as the reasoning layer, tested Python for the money math.

**Live demo:** https://bells-of-steel-freight-audit.vercel.app  (open it, then hit "Audit all invoices")

---

## Why this one first

You have said publicly that the jump past $10M broke your processes and that margins suffered under a patchwork of tools. Freight is where that leak is largest for an oversized-equipment brand: reweighs above the BOL, fuel surcharges above the agreed percentage, unauthorized detention and residential fees, and 2 to 5 percent of LTL shipments arriving damaged. Most of it is never disputed because nobody has time to check every carrier invoice line by line. This copilot does, and it reports a dollar number, which is the language an EOS Rock speaks in.

So instead of pitching, we built it. The demo audits real-shaped Day and Ross, Old Dominion and XPO invoices and shows the recoverable total climbing. The same logic runs as real Python here.

## How it works, on your stack

```
EasyPost + Brightpearl        carrier invoice PDF
   (quote + BOL)                 (Day & Ross, LTL)
        \                          /
         v                        v
            Claude (reads + normalizes, function-calling)
                         |
                         v
              auditor.py  ->  flagged lines + $ recoverable
                         |
                         v
        drafted dispute email  ->  Brightpearl (log recovery)
```

Claude reads the messy PDF and normalizes it; it never invents the numbers. It calls `audit_invoice()` and reports exactly what the engine returns. The money math is deterministic and tested, so every disputed dollar is defensible.

## Real code in this repo

- `auditor.py` - the deterministic audit engine. Reweigh, fuel surcharge, unauthorized accessorial and linehaul checks, each returning the exact recoverable amount.
- `claude_agent.py` - the Claude function-calling wiring. Claude parses the PDF and drafts the dispute; the auditor owns the math.
- `test_auditor.py` - proves the ordering and the numbers: reweighs caught, tolerances respected, clean invoices pass, disputes cite only flagged lines.

```
pip install -r requirements.txt
pytest                      # audit math tests
python auditor.py           # sample audit + drafted dispute
```

## Answers to your five questions

**1. Have you built with Claude, and do you lead with your code or with Claude?**
Yes. We lead with Claude as architect and reasoning layer and keep the critical logic in tested Python. Here Claude reads and normalizes the invoice and drafts the dispute; `auditor.py` owns the dollars. AI for judgment, code for correctness.

**2. Which of our platforms have you integrated?**
API and webhook integrations across Shopify, Amazon SP-API, and shipping and ERP systems of this shape (EasyPost quotes and BOLs, Brightpearl orders and inventory, Gorgias tickets). This copilot is wired to exactly those touchpoints.

**3. An internal tool you built end to end, in production.**
We build and ship live tools, not prototypes. Two public examples with running demos and tested code: a Claude-driven cyber-readiness console and an offline-first data-durability engine (links in the proposal). This freight copilot is the same pattern applied to your margin leak: problem (untracked carrier overbilling), solution (line-by-line AI audit plus drafted dispute), outcome (recovered dollars per invoice).

**4. Recent similar work.**
AI copilots and workflow automations that pull live data from commerce and ops systems, draft actions for a human to approve, and log the result. Scoped in 1 to 2 week sprints, shipped iteratively.

**5. GitHub / website.**
This repo, plus the demos linked in the proposal.

---

Built by the **CrewNexa** team. You own the spec and the stack, we ship the tools.
