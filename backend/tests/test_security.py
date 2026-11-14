"""认证工具单测。"""
from __future__ import annotations

from src.utils.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_roundtrip():
    hashed = hash_password("Demo@2026")
    assert hashed != "Demo@2026"
    assert verify_password("Demo@2026", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_token_roundtrip():
    token, expires_in = create_access_token("admin@example.io", "admin")
    assert expires_in > 0
    payload = decode_access_token(token)
    assert payload["sub"] == "admin@example.io"
    assert payload["role"] == "admin"


def test_invalid_token():
    assert decode_access_token("not-a-token") is None
