"""
quota.py
─────────────────────────────────────────────────────────────
Token-based quota system for AMC 8 智学助手

Design:
  • Per-user daily quota: QUOTA_PER_USER tokens
  • Global daily quota:   QUOTA_GLOBAL tokens (≈ $1)
  • Circuit breaker triggers when daily cost ≥ COST_LIMIT_USD
  • Users with their own API key bypass everything
  • Date-keyed (YYYY-MM-DD UTC) so quotas auto-reset at 0:00 UTC

Storage:
  Single JSON file (usage.json). Accepts file loss on container restart.
  Locking is best-effort via a file lock; collisions are rare at this scale.

User identification:
  hash(cookie_uuid + ip_first_3_octets + ua_browser_family)
"""

from __future__ import annotations
import json
import os
import re
import hashlib
import threading
from datetime import datetime, timezone
from typing import Any

# ─── Tunable Constants ──────────────────────────────────────────────────────
QUOTA_PER_USER  = 50_000        # tokens per user per day
QUOTA_GLOBAL    = 4_000_000     # tokens globally per day
COST_LIMIT_USD  = 1.0           # circuit breaker threshold
SOFT_WARN_RATIO = 0.80          # show "consider your own key" prompt at 80%
EVENT_BUFFER    = 1000          # keep last N events for admin view

# Gemini 2.5 Flash pricing (USD per token)
PRICE_INPUT_PER_TOKEN  = 0.075 / 1_000_000   # $0.075 per 1M tokens
PRICE_OUTPUT_PER_TOKEN = 0.30  / 1_000_000   # $0.30  per 1M tokens

USAGE_FILE = "usage.json"
_FILE_LOCK = threading.Lock()


# ─── Errors ────────────────────────────────────────────────────────────────
class QuotaError(Exception):
    """Raised when a call would exceed any quota or the breaker is tripped."""
    def __init__(self, message: str, kind: str = "generic"):
        super().__init__(message)
        self.kind = kind  # 'user' | 'global' | 'breaker' | 'generic'


# ─── Date helper ────────────────────────────────────────────────────────────
def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ─── Storage ───────────────────────────────────────────────────────────────
def _empty_usage():
    return {"by_user": {}, "global": {}, "events": []}


def _load() -> dict:
    if not os.path.exists(USAGE_FILE):
        return _empty_usage()
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Validate shape
        for k in ("by_user", "global", "events"):
            data.setdefault(k, _empty_usage()[k])
        return data
    except Exception:
        return _empty_usage()


def _save(data: dict) -> None:
    # Trim events buffer
    if len(data.get("events", [])) > EVENT_BUFFER:
        data["events"] = data["events"][-EVENT_BUFFER:]
    try:
        tmp = USAGE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, USAGE_FILE)
    except Exception:
        # Best-effort; quota is not critical-correctness data
        pass


def _atomic(fn):
    """Decorator: load, mutate, save under a thread lock."""
    def wrapper(*args, **kwargs):
        with _FILE_LOCK:
            data = _load()
            result = fn(data, *args, **kwargs)
            _save(data)
            return result
    return wrapper


# ─── User identification ────────────────────────────────────────────────────
def make_user_hash(cookie_id: str | None, ip: str | None,
                   user_agent: str | None) -> str:
    """Create a stable hash that survives:
        - browser updates (UA family only)
        - mobile IP last-octet changes (first 3 octets only)
    But changes when the user clears Cookie AND switches network.
    """
    parts = []

    if cookie_id:
        parts.append(str(cookie_id))
    else:
        parts.append("anon")

    if ip:
        # Take first 3 octets only
        m = re.match(r"^(\d+\.\d+\.\d+)\.\d+", ip)
        parts.append(m.group(1) if m else ip[:32])
    else:
        parts.append("noip")

    if user_agent:
        # Browser family (e.g. "Chrome", "Safari", "Firefox")
        m = re.search(r"(Chrome|Safari|Firefox|Edge|Opera|Mobile)", user_agent)
        parts.append(m.group(1) if m else "other")
    else:
        parts.append("noua")

    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ─── Read helpers ──────────────────────────────────────────────────────────
def get_user_today(user_hash: str) -> dict:
    """Return today's stats for a user.
    Shape: {tokens_used, calls, cost_usd, remaining, pct_used}"""
    data = _load()
    today = today_utc()
    record = data["by_user"].get(user_hash, {}).get(today, {
        "tokens_used": 0, "calls": 0, "cost_usd": 0.0,
    })
    used = record.get("tokens_used", 0)
    return {
        "tokens_used": used,
        "calls":       record.get("calls", 0),
        "cost_usd":    record.get("cost_usd", 0.0),
        "remaining":   max(0, QUOTA_PER_USER - used),
        "pct_used":    min(100, int(100 * used / QUOTA_PER_USER)) if QUOTA_PER_USER else 0,
    }


def get_global_today() -> dict:
    """Return today's global stats.
    Shape: {tokens_used, calls, cost_usd, circuit_broken, remaining_tokens, pct_cost}"""
    data = _load()
    today = today_utc()
    g = data["global"].get(today, {
        "tokens_used": 0, "calls": 0, "cost_usd": 0.0, "circuit_breaker": False,
    })
    used = g.get("tokens_used", 0)
    cost = g.get("cost_usd", 0.0)
    return {
        "tokens_used":      used,
        "calls":            g.get("calls", 0),
        "cost_usd":         cost,
        "circuit_broken":   bool(g.get("circuit_breaker", False)),
        "remaining_tokens": max(0, QUOTA_GLOBAL - used),
        "pct_cost":         min(100, int(100 * cost / COST_LIMIT_USD)) if COST_LIMIT_USD else 0,
    }


def is_circuit_broken() -> bool:
    return get_global_today()["circuit_broken"]


# ─── Pre-call check ────────────────────────────────────────────────────────
def can_call(user_hash: str, est_input_tokens: int = 2000,
             est_output_tokens: int = 1000) -> tuple[bool, str | None]:
    """Check if a call is allowed given current quotas.
    Returns (ok, reason_if_not_ok). Use estimates of expected token cost."""
    g = get_global_today()
    if g["circuit_broken"]:
        return False, "今日免费层已熔断（成本超限）。请填入您自己的 Gemini API Key 继续使用。"

    estimated = est_input_tokens + est_output_tokens

    if g["remaining_tokens"] < estimated:
        return False, "今日全站免费额度已耗尽。明天 0:00 (UTC) 自动重置。"

    u = get_user_today(user_hash)
    if u["remaining"] < estimated:
        remaining_k = u["remaining"] / 1000
        return False, (
            f"您今日的免费额度已不足（剩余约 {remaining_k:.1f}K tokens，"
            f"本次调用需要约 {estimated/1000:.1f}K）。\n\n"
            f"建议：填入您自己的 Gemini API Key 即可无限使用，"
            f"或等明天 0:00 (UTC) 自动重置。"
        )

    return True, None


# ─── Recording usage ───────────────────────────────────────────────────────
@_atomic
def record_usage(data: dict, user_hash: str, action: str,
                 input_tokens: int, output_tokens: int) -> dict:
    """Record one API call. Returns updated usage info + breaker status."""
    today = today_utc()
    total = (input_tokens or 0) + (output_tokens or 0)
    cost = (
        (input_tokens or 0) * PRICE_INPUT_PER_TOKEN +
        (output_tokens or 0) * PRICE_OUTPUT_PER_TOKEN
    )

    # Per-user
    user_bucket = data["by_user"].setdefault(user_hash, {})
    user_today = user_bucket.setdefault(today, {
        "tokens_used": 0, "calls": 0, "cost_usd": 0.0,
    })
    user_today["tokens_used"] += total
    user_today["calls"] += 1
    user_today["cost_usd"] += cost

    # Global
    g_today = data["global"].setdefault(today, {
        "tokens_used": 0, "calls": 0, "cost_usd": 0.0, "circuit_breaker": False,
    })
    g_today["tokens_used"] += total
    g_today["calls"] += 1
    g_today["cost_usd"] += cost

    # Trip breaker if cost exceeds limit
    if g_today["cost_usd"] >= COST_LIMIT_USD and not g_today["circuit_breaker"]:
        g_today["circuit_breaker"] = True

    # Event log
    data["events"].append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": user_hash,
        "action": action,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "cost_usd": round(cost, 6),
    })

    return {
        "user_remaining": max(0, QUOTA_PER_USER - user_today["tokens_used"]),
        "user_pct":       min(100, int(100 * user_today["tokens_used"] / QUOTA_PER_USER)),
        "global_cost":    g_today["cost_usd"],
        "circuit_broken": g_today["circuit_breaker"],
    }


# ─── Admin actions ─────────────────────────────────────────────────────────
@_atomic
def admin_reset_user(data: dict, user_hash: str, date: str | None = None) -> bool:
    date = date or today_utc()
    if user_hash in data["by_user"]:
        if date in data["by_user"][user_hash]:
            del data["by_user"][user_hash][date]
            return True
    return False


@_atomic
def admin_set_breaker(data: dict, on: bool) -> None:
    today = today_utc()
    g = data["global"].setdefault(today, {
        "tokens_used": 0, "calls": 0, "cost_usd": 0.0, "circuit_breaker": False,
    })
    g["circuit_breaker"] = bool(on)


@_atomic
def admin_clear_today(data: dict) -> None:
    today = today_utc()
    data["global"].pop(today, None)
    for u in list(data["by_user"].keys()):
        data["by_user"][u].pop(today, None)
        if not data["by_user"][u]:
            del data["by_user"][u]
    # Also remove today's events
    today_prefix = today
    data["events"] = [e for e in data["events"]
                      if not e.get("ts", "").startswith(today_prefix)]


@_atomic
def admin_clear_all(data: dict) -> None:
    data["by_user"] = {}
    data["global"] = {}
    data["events"] = []


# ─── Admin views ───────────────────────────────────────────────────────────
def get_top_users_today(n: int = 10) -> list[dict]:
    data = _load()
    today = today_utc()
    rows = []
    for uh, daily in data["by_user"].items():
        rec = daily.get(today)
        if rec and rec.get("tokens_used", 0) > 0:
            rows.append({
                "user": uh,
                "tokens": rec["tokens_used"],
                "calls": rec["calls"],
                "cost": rec["cost_usd"],
            })
    rows.sort(key=lambda r: r["tokens"], reverse=True)
    return rows[:n]


def get_recent_days(n: int = 7) -> list[dict]:
    """Return [{date, tokens, calls, cost}, ...] sorted oldest→newest."""
    data = _load()
    out = []
    for date, g in data["global"].items():
        out.append({
            "date":   date,
            "tokens": g.get("tokens_used", 0),
            "calls":  g.get("calls", 0),
            "cost":   g.get("cost_usd", 0.0),
        })
    out.sort(key=lambda r: r["date"])
    return out[-n:]


def get_recent_events(n: int = 50) -> list[dict]:
    data = _load()
    return data["events"][-n:][::-1]
