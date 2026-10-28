"""LiteLLM callback: keeps logs/usage.json with today's use per free provider.

The token-counter mod reads that file to draw the "tokens left today" bar.
Days are UTC, which is when OpenRouter's free limit resets.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from litellm.integrations.custom_logger import CustomLogger

ROOT = Path(__file__).parent
USAGE_FILE = ROOT / "logs" / "usage.json"

# Free limits as each provider publishes them. None = not published.
# (limit, window) where window is "day" or "hour".
LIMITS = {
    "openrouter": (50, "day"),  # 1,000 once the account has bought credits; checked below
    "groq": (2000, "day"),  # about 1,000 per model, two models
    "kilo": (200, "hour"),  # per IP, no account
    "gemini": (None, "day"),
    "zai": (None, "day"),  # no daily cap, one request at a time
    "llm7": (None, "day"),
    "nvidia": (None, "day"),
    "mistral": (None, "day"),
}

# For the single "tokens left today" bar: each provider's daily limit turned into
# tokens. A request limit times the average request size; Groq caps tokens itself.
# Z.ai and LLM7 publish no limit, so they are extra on top of this estimate.
AVG_REQUEST_TOKENS = 30_000  # used until the router has measured a few requests
TOKEN_CAPS = {"groq": 400_000}  # about 200K a day per model, two models
DAILY_REQUESTS = {
    "nvidia": 1000,  # sources say 1,000 to 10,000 a day; the low end
    "gemini": 250,  # Flash on a free key
    "kilo": 200 * 24,  # 200 an hour
}
BUDGET_KEYS = {
    "nvidia": "NVIDIA_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "kilo": None,  # no sign-up
}


def provider_of(payload):
    model = (payload.get("model") or "").lower()
    api_base = (payload.get("api_base") or "").lower()
    custom = (payload.get("custom_llm_provider") or "").lower()
    for name, needle in (
        ("kilo", "kilo.ai"),
        ("llm7", "llm7.io"),
        ("zai", "z.ai"),
        ("nvidia", "nvidia.com"),
    ):
        if needle in api_base:
            return name
    for name in ("openrouter", "groq", "gemini", "mistral"):
        if custom == name or model.startswith(name + "/") or name in api_base:
            return name
    return custom or "other"


class UsageLogger(CustomLogger):
    def __init__(self):
        super().__init__()
        self.openrouter_paid = None
        self.openrouter_checked = 0.0
        # so the bar has numbers before the first request of the day
        self.save(self.load())

    def load(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            data = json.loads(USAGE_FILE.read_text())
        except (OSError, ValueError):
            data = {}
        if data.get("day") != today:
            data = {"day": today, "providers": {}}
        return data

    def budget(self, data):
        providers = data["providers"].values()
        requests = sum(p["requests"] for p in providers)
        tokens = sum(p["tokens"] for p in providers)
        avg = tokens // requests if requests >= 5 else AVG_REQUEST_TOKENS
        total = left = 0
        for name, key in BUDGET_KEYS.items():
            if key and not os.environ.get(key):
                continue
            if name in TOKEN_CAPS:
                daily = TOKEN_CAPS[name]
            elif name == "openrouter":
                daily = (1000 if self.openrouter_paid else 50) * avg
            else:
                daily = DAILY_REQUESTS[name] * avg
            used = data["providers"].get(name, {}).get("tokens", 0)
            total += daily
            left += max(0, daily - used)
        data["budget"] = {"total": total, "left": left, "avgRequest": avg}

    def save(self, data):
        self.budget(data)
        data["updated"] = time.time()
        tmp = USAGE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        os.replace(tmp, USAGE_FILE)

    async def check_openrouter_plan(self):
        # is_free_tier turns false once credits were bought: limit goes 50 -> 1,000 a day
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key or time.time() - self.openrouter_checked < 3600:
            return
        self.openrouter_checked = time.time()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://openrouter.ai/api/v1/key",
                    headers={"Authorization": f"Bearer {key}"},
                )
            self.openrouter_paid = r.json()["data"].get("is_free_tier") is False
        except Exception:
            pass

    def entry(self, data, name):
        limit, window = LIMITS.get(name, (None, "day"))
        if name == "openrouter" and self.openrouter_paid:
            limit = 1000
        entry = data["providers"].setdefault(
            name, {"requests": 0, "tokens": 0, "recent": [], "limitedAt": None}
        )
        entry["limit"] = limit
        entry["window"] = window
        hour_ago = time.time() - 3600
        entry["recent"] = [t for t in entry["recent"] if t > hour_ago]
        return entry

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        payload = kwargs.get("standard_logging_object") or {}
        name = provider_of(payload)
        if name == "openrouter":
            await self.check_openrouter_plan()
        data = self.load()
        entry = self.entry(data, name)
        entry["requests"] += 1
        entry["tokens"] += int(payload.get("total_tokens") or 0)
        entry["recent"].append(time.time())
        headers = (payload.get("hidden_params") or {}).get("additional_headers") or {}
        if headers.get("x_ratelimit_remaining_requests") is not None:
            entry["remainingRequests"] = headers["x_ratelimit_remaining_requests"]
        self.save(data)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        payload = kwargs.get("standard_logging_object") or {}
        error = payload.get("error_information") or {}
        if str(error.get("error_code")) != "429":
            return
        data = self.load()
        self.entry(data, provider_of(payload))["limitedAt"] = time.time()
        self.save(data)


usage_logger = UsageLogger()
