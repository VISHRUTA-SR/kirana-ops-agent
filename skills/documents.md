# Documents Skill

Tools: `generate_invoice_pdf`, `generate_analysis_deck`.

- `generate_invoice_pdf` renders `templates/invoice.html` (Jinja2) with
  WeasyPrint into a real GST invoice PDF — tax breakup table, HSN codes,
  CGST/SGST columns. Only works on a finalized bill.
- `generate_analysis_deck` builds a PPTX with native python-pptx chart
  objects (line, bar, pie) — not embedded images — from live analytics
  data: sales trend, top items, payment split, reorder list.
