"""Kịch bản test tải 20 "user" đồng thời ở TẦNG SERVICE/DB — bước 6.2.

Đây là SCRIPT CHẨN ĐOÁN (không phải code sản phẩm) — không cần tuân theo
tách lớp `src/app/`, nhưng vẫn dùng ĐÚNG `compute_data_scope()` thật (không
giả lập RBAC bằng tay) để mô phỏng đúng tải thật của service layer.

Vì sao test ở tầng service/DB thay vì qua UI Streamlit (COO xác nhận
11/09/2026, bước 6.2): Streamlit dùng WebSocket + cơ chế rerun toàn trang
cho mỗi tương tác, không khớp với công cụ load-test HTTP thông thường
(Locust/k6 giả lập request-response). Tầng chịu tải thật khi nhiều người
dùng cùng lúc là service/DB (query + connection pool), không phải bản thân
Streamlit — script này đo đúng tầng đó.

Cách dùng: `python scripts/load_test_services.py` (từ thư mục gốc repo,
cần `.env` trỏ đúng MySQL "lacco" thật — dùng chính DB dự án, không phải
SQLite test).
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.scope import DataScope, compute_data_scope
from src.db.models import User
from src.services import (
    report_chi_phi,
    report_cong_no,
    report_don_hang,
    report_khach_hang,
    report_kinh_doanh,
    report_pricing,
)
from src.services.db_connection import get_engine

_DURATION_SECONDS = 60
_TARGET_CONCURRENT_USERS = 20
_SLEEP_BETWEEN_CALLS = (2.0, 3.0)  # giây, random.uniform mỗi vòng lặp

# 1 hàm đại diện (đầu tiên/đơn giản nhất) cho mỗi module báo cáo trong 6
# nhóm báo cáo — KHÔNG phải toàn bộ hàm, đúng phạm vi bước 6.2 (chẩn đoán
# tải, không phải test coverage đầy đủ từng hàm).
_REPRESENTATIVE_FUNCTIONS: dict[str, callable] = {
    "kinh_doanh.get_revenue_profit_by_service": report_kinh_doanh.get_revenue_profit_by_service,
    "khach_hang.get_classification_trend": report_khach_hang.get_classification_trend,
    "don_hang.get_order_status_counts": report_don_hang.get_order_status_counts,
    "pricing.get_win_rate_by_org": report_pricing.get_win_rate_by_org,
    "chi_phi.get_cost_vs_budget_by_division": report_chi_phi.get_cost_vs_budget_by_division,
    "cong_no.get_debt_aging_summary": report_cong_no.get_debt_aging_summary,
}


@dataclass
class CallRecord:
    function_name: str
    elapsed_seconds: float
    error: str | None = None


@dataclass
class WorkerResult:
    user_id: int
    records: list[CallRecord] = field(default_factory=list)


def _fetch_user_ids(engine, limit: int) -> list[int]:
    """Lấy tối đa `limit` `users.id` thật từ DB — không giả lập."""
    with Session(engine) as session:
        stmt = select(User.id).order_by(User.id).limit(limit)
        return [row[0] for row in session.execute(stmt).all()]


def _worker(user_id: int, scope: DataScope, engine, end_time: float) -> WorkerResult:
    """Mô phỏng 1 user: lặp gọi ngẫu nhiên 1 trong 6 hàm đại diện, mỗi
    2-3 giây, cho tới khi hết `end_time`."""
    result = WorkerResult(user_id=user_id)
    names = list(_REPRESENTATIVE_FUNCTIONS.keys())
    while time.time() < end_time:
        name = random.choice(names)
        fn = _REPRESENTATIVE_FUNCTIONS[name]
        t0 = time.perf_counter()
        error = None
        try:
            fn(scope, engine=engine)
        except Exception as exc:  # noqa: BLE001 - script chẩn đoán, cần bắt MỌI loại lỗi để đếm
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - t0
        result.records.append(CallRecord(function_name=name, elapsed_seconds=elapsed, error=error))
        time.sleep(random.uniform(*_SLEEP_BETWEEN_CALLS))
    return result


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    return values_sorted[f] + (values_sorted[c] - values_sorted[f]) * (k - f)


def main() -> None:
    engine = get_engine()

    real_user_ids = _fetch_user_ids(engine, _TARGET_CONCURRENT_USERS)
    if not real_user_ids:
        raise RuntimeError("Không tìm thấy user nào trong bảng users — không thể chạy load test.")

    logger.info(
        "load_test_services: tìm thấy {} user thật trong DB (cần {}).",
        len(real_user_ids),
        _TARGET_CONCURRENT_USERS,
    )

    # Nếu DB có ít hơn 20 user, lặp lại danh sách cho đủ 20 "luồng ảo" —
    # ghi rõ số lượng THẬT ở trên, không đánh lừa là 20 user riêng biệt.
    user_ids_for_threads = [
        real_user_ids[i % len(real_user_ids)] for i in range(_TARGET_CONCURRENT_USERS)
    ]

    logger.info("load_test_services: tính compute_data_scope() 1 lần cho mỗi user...")
    scopes: dict[int, DataScope] = {}
    for uid in set(user_ids_for_threads):
        scopes[uid] = compute_data_scope(uid, engine=engine)

    end_time = time.time() + _DURATION_SECONDS
    logger.info(
        "load_test_services: chạy {} luồng đồng thời trong {}s...",
        _TARGET_CONCURRENT_USERS,
        _DURATION_SECONDS,
    )

    worker_results: list[WorkerResult] = []
    with ThreadPoolExecutor(max_workers=_TARGET_CONCURRENT_USERS) as executor:
        futures = [
            executor.submit(_worker, uid, scopes[uid], engine, end_time)
            for uid in user_ids_for_threads
        ]
        for future in futures:
            worker_results.append(future.result())

    per_function: dict[str, list[CallRecord]] = defaultdict(list)
    for wr in worker_results:
        for rec in wr.records:
            per_function[rec.function_name].append(rec)

    print(f"\nSố user thật trong DB: {len(real_user_ids)} (mục tiêu {_TARGET_CONCURRENT_USERS})")
    print(f"Thời lượng chạy: {_DURATION_SECONDS}s | Số luồng đồng thời: {_TARGET_CONCURRENT_USERS}\n")

    header = (
        f"{'Hàm':<45}{'Số lần':>8}{'Min(s)':>9}{'Max(s)':>9}"
        f"{'Avg(s)':>9}{'P95(s)':>9}{'Lỗi':>6}"
    )
    print(header)
    print("-" * len(header))

    total_calls = 0
    total_errors = 0
    error_details: dict[str, list[str]] = defaultdict(list)

    for name, records in sorted(per_function.items()):
        ok_times = [r.elapsed_seconds for r in records if r.error is None]
        errors = [r for r in records if r.error is not None]
        total_calls += len(records)
        total_errors += len(errors)
        for r in errors:
            error_details[name].append(r.error)

        if ok_times:
            row = (
                f"{name:<45}{len(records):>8}{min(ok_times):>9.3f}{max(ok_times):>9.3f}"
                f"{statistics.mean(ok_times):>9.3f}{_percentile(ok_times, 0.95):>9.3f}"
                f"{len(errors):>6}"
            )
        else:
            row = f"{name:<45}{len(records):>8}{'—':>9}{'—':>9}{'—':>9}{'—':>9}{len(errors):>6}"
        print(row)

    print(f"\nTổng số lần gọi: {total_calls} | Tổng số lỗi: {total_errors}")

    if error_details:
        print("\nChi tiết lỗi (tối đa 5 dòng/hàm):")
        for name, errs in error_details.items():
            print(f"  {name}:")
            for e in errs[:5]:
                print(f"    - {e}")


if __name__ == "__main__":
    main()
