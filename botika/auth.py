"""Password hashing and login rules (standard library only).

Passwords are never stored: only a salted PBKDF2 hash is kept in the database.
"""
import hashlib
import hmac
import os
import re

ITERATIONS = 200_000
ROLE_ADMIN = "ADMIN"
ROLE_STAFF = "STAFF"
ROLE_LABELS = {ROLE_ADMIN: "Admin", ROLE_STAFF: "Staff"}
MIN_PASSWORD_LENGTH = 6
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,30}$")
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 30


class AuthError(Exception):
    """Not logged in, wrong password, or the action needs more permission."""


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iterations, salt_hex, hash_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt_hex), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def check_username(username: str) -> str:
    username = (username or "").strip()
    if not USERNAME_PATTERN.match(username):
        raise AuthError("Username must be 3-30 characters: letters, numbers, "
                        "dot, dash or underscore.")
    return username


def check_password(password: str) -> str:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password
