"""Pandera schema cho pipeline import Excel/CSV (bước 2.4).

Tách theo 3 nhóm bảng giống `src/db/models/` để dễ đối chiếu:

- `dimension_schemas.py` — division, department, employee, service,
  customer, supplier.
- `business_schemas.py` — sales_order, price_request, supplier_evaluation,
  cost, budget, personnel_cost, debt, customer_classification_history.
- `security_schemas.py` — users, login_history, audit_log (KHÔNG có schema
  cho `import_history` — bảng này do chính pipeline tự ghi log, không nhận
  import từ file).
- `registry.py` — gộp toàn bộ schema + model + cấu hình khoá ngoại vào 1
  registry dùng chung cho framework generic trong
  `src/services/import_pipeline.py`.
"""
