"""
Pure Python auth service for NiceGUI dashboard.
User & Role CRUD, password hashing, permission checks.
Uses same config directory as streamlit_template for data persistence.
"""
import os
import json
import secrets
import hashlib
import time
from pathlib import Path
from typing import Optional, List

# Path: .../difotoin-dashboard/nicegui_template/services/auth_service.py
# We need: .../difotoin-dashboard/streamlit_template/config/
BASE_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"
CONFIG_DIR = BASE_DIR / "config"
USERS_PATH = CONFIG_DIR / "users.json"
ROLES_PATH = CONFIG_DIR / "roles.json"

# ── All known NAV routes ──
ALL_ROUTES = [
    "/", "/trend", "/ai-decision", "/conversion", "/ranking",
    "/kemitraan", "/lead-partnership", "/lead-kemitraan",
    "/comparison", "/crud", "/admin", "/upload",
]

# ── Default roles (used as fallback) ──
DEFAULT_ROLES = {
    "admin": ALL_ROUTES,
    "manager": ["/", "/trend", "/conversion", "/ranking", "/kemitraan",
                "/lead-partnership", "/lead-kemitraan", "/comparison"],
    "staff": ["/", "/ranking", "/kemitraan", "/lead-partnership", "/lead-kemitraan"],
    "viewer": ["/"],
}


# ═══════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════

def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    )
    return salt, digest.hex()


def _verify_password(password: str, salt: str, password_hash: str) -> bool:
    if not password or not salt or not password_hash:
        return False
    _, digest = _hash_password(password, salt)
    return secrets.compare_digest(digest, password_hash)


# ═══════════════════════════════════════════════
#  USERS
# ═══════════════════════════════════════════════

def load_users() -> List[dict]:
    try:
        with open(USERS_PATH, "r") as f:
            data = json.load(f)
        users = data.get("users", []) if isinstance(data, dict) else []
        return users if isinstance(users, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_users(users: List[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(USERS_PATH, "w") as f:
        json.dump({"users": users}, f, indent=2)


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate user. Returns user dict or None."""
    email_norm = _normalize_email(email)
    for user in load_users():
        if (_normalize_email(user.get("email", "")) == email_norm
                and _verify_password(password, user.get("salt", ""), user.get("password_hash", ""))):
            user_dict = dict(user)
            user_dict.pop("salt", None)
            user_dict.pop("password_hash", None)
            return user_dict
    # Fallback to env var admin
    admin_email = os.getenv("DIFOTOIN_ADMIN_EMAIL")
    admin_pass = os.getenv("DIFOTOIN_ADMIN_PASSWORD")
    if admin_email and admin_pass:
        if _normalize_email(admin_email) == email_norm and password == admin_pass:
            return {"name": "Admin", "email": admin_email, "role": "admin", "source": "env"}
    return None


def create_user(name: str, email: str, password: str, role: str = "viewer") -> Optional[dict]:
    """Create a new user. Returns user dict or None if email exists."""
    email = _normalize_email(email)
    if any(_normalize_email(u.get("email")) == email for u in load_users()):
        return None
    salt, pw_hash = _hash_password(password)
    user = {
        "name": name,
        "email": email,
        "salt": salt,
        "password_hash": pw_hash,
        "role": role,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    users = load_users()
    users.append(user)
    save_users(users)
    return {"name": name, "email": email, "role": role}


def update_user(email: str, updates: dict) -> bool:
    """Update user fields. Supports: name, role, password."""
    email = _normalize_email(email)
    users = load_users()
    for i, u in enumerate(users):
        if _normalize_email(u.get("email")) == email:
            for k, v in updates.items():
                if k == "password":
                    salt, pw_hash = _hash_password(v)
                    u["salt"] = salt
                    u["password_hash"] = pw_hash
                elif k in ("name", "role"):
                    u[k] = v
            u["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            users[i] = u
            save_users(users)
            return True
    return False


def delete_users(emails: List[str]) -> int:
    """Delete users by email. Returns count deleted."""
    norm = set(_normalize_email(e) for e in emails)
    remaining = [u for u in load_users() if _normalize_email(u.get("email")) not in norm]
    deleted = len(load_users()) - len(remaining)
    save_users(remaining)
    return deleted


# ═══════════════════════════════════════════════
#  ROLES
# ═══════════════════════════════════════════════

def load_roles() -> List[dict]:
    """Load roles from roles.json. Falls back to built-in defaults."""
    try:
        with open(ROLES_PATH, "r") as f:
            data = json.load(f)
        roles = data.get("roles", []) if isinstance(data, dict) else data
        if isinstance(roles, list) and len(roles) > 0:
            return roles
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # First-run: seed defaults
    roles = [{"name": name, "permissions": perms} for name, perms in DEFAULT_ROLES.items()]
    save_roles(roles)
    return roles


def save_roles(roles: List[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ROLES_PATH, "w") as f:
        json.dump({"roles": roles}, f, indent=2)


def get_role_permissions(role_name: str) -> List[str]:
    """Get permitted routes for a role."""
    for r in load_roles():
        if r.get("name") == role_name:
            return r.get("permissions", [])
    return DEFAULT_ROLES.get(role_name, [])


def has_permission(role_name: str, route: str) -> bool:
    """Check if a role may access a route."""
    if role_name == "admin":
        return True
    return route in get_role_permissions(role_name)


def get_allowed_routes(role_name: str) -> List[str]:
    """All routes a role may access (for filtering the nav drawer)."""
    if role_name == "admin":
        return ALL_ROUTES.copy()
    return get_role_permissions(role_name)


def create_role(name: str, permissions: List[str]) -> Optional[dict]:
    """Create a new role."""
    if any(r.get("name") == name for r in load_roles()):
        return None
    role = {"name": name, "permissions": permissions}
    roles = load_roles()
    roles.append(role)
    save_roles(roles)
    return role


def update_role(name: str, new_name: Optional[str] = None, permissions: Optional[List[str]] = None) -> bool:
    """Update role name / permissions."""
    roles = load_roles()
    for r in roles:
        if r.get("name") == name:
            if new_name is not None:
                r["name"] = new_name
            if permissions is not None:
                r["permissions"] = permissions
            save_roles(roles)
            return True
    return False


def delete_role(name: str) -> bool:
    """Delete a role. Cannot delete 'admin'."""
    if name == "admin":
        return False
    roles = [r for r in load_roles() if r.get("name") != name]
    save_roles(roles)
    return True


def fix_existing_users_roles():
    """Migrate existing users (no role field) to have a default 'viewer' role."""
    users = load_users()
    changed = False
    for u in users:
        if "role" not in u or not u.get("role"):
            u["role"] = "viewer"
            changed = True
    if changed:
        save_users(users)
