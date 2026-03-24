"""
ATLAST Local Config — ~/.atlast/config.json

Stores agent_did, agent_api_key, endpoint after registration.
Priority for all settings: CLI args > env vars > config file > defaults.
"""

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_ENDPOINT = "https://api.weba0.com/v1"  # ATLAST ECP Server (override via ATLAST_API_URL env or atlast init)
CONFIG_DIR = Path.home() / ".atlast"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_config_path() -> Path:
    return CONFIG_FILE


def load_config() -> dict:
    """Load local config. Returns {} if not exists or invalid."""
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except Exception:
        pass
    return {}


def save_config(data: dict):
    """
    Save config to ~/.atlast/config.json. Creates dir if needed.
    Note: load-merge-write is NOT atomic. Safe for single-process CLI use.
    Multi-process safety would require file locking (not needed for Phase 1).
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Merge with existing
    existing = load_config()
    existing.update(data)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2))


def get_api_url() -> str:
    """
    Get API URL with priority: env ATLAST_API_URL > config endpoint > default.
    Always ensures the URL ends with /v1 (the API prefix).
    """
    env_url = os.environ.get("ATLAST_API_URL")
    if env_url:
        url = env_url.rstrip("/")
        if not url.endswith("/v1"):
            url = url + "/v1"
        return url
    cfg = load_config()
    if cfg.get("endpoint"):
        url = cfg["endpoint"].rstrip("/")
        if not url.endswith("/v1"):
            url = url + "/v1"
        return url
    return DEFAULT_ENDPOINT


def get_api_key() -> Optional[str]:
    """
    Get API key with priority: env ATLAST_API_KEY > config agent_api_key > None.
    """
    env_key = os.environ.get("ATLAST_API_KEY")
    if env_key:
        return env_key
    cfg = load_config()
    return cfg.get("agent_api_key") or None


def get_webhook_url() -> Optional[str]:
    """Get webhook URL: env ECP_WEBHOOK_URL > config webhook_url > None."""
    env = os.environ.get("ECP_WEBHOOK_URL")
    if env:
        return env.rstrip("/")
    cfg = load_config()
    return cfg.get("webhook_url") or None


def get_webhook_token() -> Optional[str]:
    """Get webhook token: env ECP_WEBHOOK_TOKEN > config webhook_token > None."""
    env = os.environ.get("ECP_WEBHOOK_TOKEN")
    if env:
        return env
    cfg = load_config()
    return cfg.get("webhook_token") or None


def get_vault_backup_path() -> Optional[str]:
    """Get vault backup path: env ATLAST_VAULT_BACKUP > config vault_backup_path > None."""
    env = os.environ.get("ATLAST_VAULT_BACKUP")
    if env:
        return env
    cfg = load_config()
    return cfg.get("vault_backup_path") or None


def get_storage_compress() -> bool:
    """Get storage compression setting: env ECP_STORAGE_COMPRESS > False (default off)."""
    val = os.environ.get("ECP_STORAGE_COMPRESS", "").lower()
    return val in ("true", "1", "yes")


def get_storage_ttl_days() -> int:
    """Get TTL days for record cleanup: env ECP_STORAGE_TTL_DAYS > 0 (disabled)."""
    val = os.environ.get("ECP_STORAGE_TTL_DAYS", "0")
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def get_vault_mode() -> str:
    """Get vault mode: env ECP_VAULT_MODE > 'full'. Values: full|hash_only|compact."""
    val = os.environ.get("ECP_VAULT_MODE", "full").lower()
    if val in ("full", "hash_only", "compact"):
        return val
    return "full"
