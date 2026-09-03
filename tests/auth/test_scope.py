"""Test `src/auth/scope.py::compute_data_scope()` — 3 nhánh RBAC theo
CLAUDE.md mục 6: Admin (unrestricted), Manager (phạm vi theo Department),
User (phạm vi theo Employee). Dùng fixture `seeded_scope_data` (SQLite
in-memory, xem `tests/conftest.py`) — KHÔNG kết nối MySQL "lacco" thật.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.auth.scope import compute_data_scope
from src.db.models.enums import UserRole
from src.db.models.security import User


def _create_user(engine, *, username: str, role: UserRole, employee_id: int | None) -> int:
    """Tạo 1 user tối thiểu qua ORM — `password_hash` là placeholder vì
    `compute_data_scope()` không kiểm tra mật khẩu."""
    with Session(engine) as session:
        user = User(
            username=username,
            password_hash="$2b$dummy-hash-not-verified",
            role=role,
            employee_id=employee_id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def test_admin_is_unrestricted_and_sees_all_customers(db_engine, seeded_scope_data):
    user_id = _create_user(
        db_engine, username="admin1", role=UserRole.ADMIN, employee_id=None
    )

    scope = compute_data_scope(user_id, engine=db_engine)

    assert scope.unrestricted is True
    assert scope.customer_ids == {
        seeded_scope_data["customer_x_id"],
        seeded_scope_data["customer_y_id"],
        seeded_scope_data["customer_z_id"],
    }


def test_manager_scope_is_by_department(db_engine, seeded_scope_data):
    user_id = _create_user(
        db_engine,
        username="manager1",
        role=UserRole.MANAGER,
        employee_id=seeded_scope_data["emp_manager_id"],
    )

    scope = compute_data_scope(user_id, engine=db_engine)

    assert scope.unrestricted is False
    assert scope.customer_ids == {
        seeded_scope_data["customer_x_id"],
        seeded_scope_data["customer_y_id"],
    }
    assert seeded_scope_data["customer_z_id"] not in scope.customer_ids


def test_user_scope_is_by_employee(db_engine, seeded_scope_data):
    user_id = _create_user(
        db_engine,
        username="user1",
        role=UserRole.USER,
        employee_id=seeded_scope_data["emp_user_id"],
    )

    scope = compute_data_scope(user_id, engine=db_engine)

    assert scope.unrestricted is False
    assert scope.customer_ids == {seeded_scope_data["customer_x_id"]}
    assert seeded_scope_data["customer_y_id"] not in scope.customer_ids
    assert seeded_scope_data["customer_z_id"] not in scope.customer_ids


def test_user_without_employee_id_has_empty_scope(db_engine, seeded_scope_data):
    user_id = _create_user(
        db_engine, username="orphan1", role=UserRole.USER, employee_id=None
    )

    scope = compute_data_scope(user_id, engine=db_engine)

    assert scope.unrestricted is False
    assert scope.customer_ids == frozenset()


def test_manager_without_employee_id_has_empty_scope(db_engine, seeded_scope_data):
    user_id = _create_user(
        db_engine, username="orphan2", role=UserRole.MANAGER, employee_id=None
    )

    scope = compute_data_scope(user_id, engine=db_engine)

    assert scope.unrestricted is False
    assert scope.customer_ids == frozenset()


def test_compute_data_scope_raises_for_unknown_user(db_engine, seeded_scope_data):
    with pytest.raises(ValueError):
        compute_data_scope(999_999, engine=db_engine)
