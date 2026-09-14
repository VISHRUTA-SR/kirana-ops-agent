# Inventory Skill

Owns product master data and stock. Tools: `add_product`, `receive_stock`,
`get_stock`, `get_low_stock`, `list_products`.

Rules enforced here, not in the prompt:
- No duplicate SKU names.
- `receive_stock` only ever increments (use `add_product` to create).
- Ambiguous product names return `{"ambiguous": true, "candidates": [...]}`
  instead of guessing — the model must ask the owner to pick one.
