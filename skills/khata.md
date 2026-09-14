# Khata (Credit Ledger) Skill

Tools: `add_credit`, `settle_credit`, `get_khata_balance`, `list_khata_customers`.

Rules enforced here, not in the prompt:
- `settle_credit` refuses if the customer has no khata record, or if
  they currently owe nothing, or if the payment exceeds the balance.
- Balance is always derived (`sum(credit) - sum(settle)`), never stored
  denormalized, so it can't drift.
