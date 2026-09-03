"""Test `src/auth/hashing.py` — không cần DB, chỉ kiểm tra bcrypt qua
`streamlit_authenticator.Hasher` (CLAUDE.md mục 3 & 6: bắt buộc bcrypt,
không tự viết hàm hash riêng)."""

from __future__ import annotations

from src.auth.hashing import hash_password, verify_password


def test_hash_password_returns_bcrypt_string():
    hashed = hash_password("mat-khau-thu-nghiem")
    assert hashed.startswith("$2b$")


def test_verify_password_true_for_correct_password():
    hashed = hash_password("mat-khau-dung")
    assert verify_password("mat-khau-dung", hashed) is True


def test_verify_password_false_for_wrong_password():
    hashed = hash_password("mat-khau-dung")
    assert verify_password("mat-khau-sai", hashed) is False


def test_hash_password_uses_random_salt_but_both_verify():
    password = "mat-khau-lap-lai"
    hash_1 = hash_password(password)
    hash_2 = hash_password(password)

    assert hash_1 != hash_2
    assert verify_password(password, hash_1) is True
    assert verify_password(password, hash_2) is True
