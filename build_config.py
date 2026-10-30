"""Write config.yaml for LiteLLM from the providers below.

Only providers whose key is set in .env are included (plus the no-key ones),
so the router never wastes time on a provider you have not signed up for.

Three model groups, each a stack of free providers:
  best  - strongest free models (Kimi, GLM, DeepSeek, Nemotron Ultra)
  good  - solid fallbacks with big context
  fast  - small and quick, for Claude Code's background jobs
Inside a group, lower `order` is tried first; when it hits a limit it cools
down and the next one takes over. When a whole group is used up, the router
falls back: best -> good, fast -> good.
"""

import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent

# (group, order, litellm model string, api_base or None, env key or None)
# env key None = no sign-up needed; "?KEY" = works without a key, KEY raises the limit.
NVIDIA = "https://integrate.api.nvidia.com/v1"
KILO = "https://api.kilo.ai/api/openrouter"
LLM7 = "https://api.llm7.io/v1"
ZAI = "https://api.z.ai/api/paas/v4"

PROVIDERS = [
    # best
    ("best", 1, "openai/moonshotai/kimi-k2.6", NVIDIA, "NVIDIA_API_KEY"),
    ("best", 1, "openai/z-ai/glm-5.3", NVIDIA, "NVIDIA_API_KEY"),
    ("best", 2, "openai/nvidia/nemotron-3-ultra-550b-a55b", NVIDIA, "NVIDIA_API_KEY"),
    ("best", 2, "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", None, "OPENROUTER_API_KEY"),
    ("best", 3, "openai/nvidia/nemotron-3-ultra-550b-a55b:free", KILO, None),
    ("best", 3, "mistral/mistral-medium-latest", None, "MISTRAL_API_KEY"),
    # good
    ("good", 1, "openai/deepseek-ai/deepseek-v4.1-flash", NVIDIA, "NVIDIA_API_KEY"),
    ("good", 1, "openai/minimaxai/minimax-m3.1-flash", NVIDIA, "NVIDIA_API_KEY"),
    ("good", 1, "openai/z-ai/glm-5.3-flash", NVIDIA, "NVIDIA_API_KEY"),
    ("good", 2, "gemini/gemini-3.5-flash", None, "GEMINI_API_KEY"),
    ("good", 2, "openai/glm-4.7-flash", ZAI, "ZAI_API_KEY"),
    ("good", 3, "openai/glm-4.5-flash", ZAI, "ZAI_API_KEY"),
    ("good", 3, "openrouter/google/gemma-4-31b-it:free", None, "OPENROUTER_API_KEY"),
    ("good", 3, "openrouter/openrouter/free", None, "OPENROUTER_API_KEY"),
    ("good", 3, "mistral/codestral-latest", None, "MISTRAL_API_KEY"),
    ("good", 4, "openai/kilo-auto/free", KILO, None),
    ("good", 4, "openai/minimax-m2.7", LLM7, "?LLM7_API_KEY"),
    # fast
    ("fast", 1, "groq/openai/gpt-oss-120b", None, "GROQ_API_KEY"),
    ("fast", 1, "groq/qwen/qwen3.8-27b", None, "GROQ_API_KEY"),
    ("fast", 1, "openai/nvidia/nemotron-3.5-lightning-30b-a3b", NVIDIA, "NVIDIA_API_KEY"),
    ("fast", 2, "gemini/gemini-3.5-flash-lite", None, "GEMINI_API_KEY"),
    ("fast", 3, "openai/gpt-oss:20b", LLM7, "?LLM7_API_KEY"),
    # read-* : one image-reading model each, no fallback, so a page score names its model
    # (added 2026-10-28 for the old-archives reading engine, ~/Desktop/free-projects/uz-old-archives)
    ("read-gemini-flash", 1, "gemini/gemini-3.5-flash", None, "GEMINI_API_KEY"),
    ("read-gemini-lite", 1, "gemini/gemini-3.5-flash-lite", None, "GEMINI_API_KEY"),
    ("read-gemma", 1, "openrouter/google/gemma-4-31b-it:free", None, "OPENROUTER_API_KEY"),
    ("read-llama-scout", 1, "groq/meta-llama/llama-4-scout-17b-16e-instruct", None, "GROQ_API_KEY"),
]


def load_env(path):
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            line = line.removeprefix("export ").strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def main():
    env = load_env(ROOT / ".env")
    model_list = []
    used = set()
    for group, order, model, api_base, key_name in PROVIDERS:
        params = {"model": model, "order": order}
        if api_base:
            params["api_base"] = api_base
        optional = bool(key_name) and key_name.startswith("?")
        key_name = key_name.lstrip("?") if key_name else None
        if key_name and env.get(key_name):
            params["api_key"] = f"os.environ/{key_name}"
            used.add(key_name)
        elif key_name and not optional:
            continue
        else:
            # Kilo and LLM7 take "anonymous" as their no-sign-up key
            params["api_key"] = "anonymous"
        model_list.append({"model_name": group, "litellm_params": params})

    config = {
        "model_list": model_list,
        "router_settings": {
            "routing_strategy": "simple-shuffle",
            "num_retries": 3,
            "allowed_fails": 1,
            "cooldown_time": 120,
            "fallbacks": [{"best": ["good"]}, {"fast": ["good"]}],
            "context_window_fallbacks": [{"fast": ["good"]}],
        },
        "litellm_settings": {
            "drop_params": True,
            # free providers only speak chat/completions, not OpenAI's newer /responses
            "use_chat_completions_url_for_anthropic_messages": True,
            # writes logs/usage.json for the token bar mod
            "callbacks": ["usage_logger.usage_logger"],
        },
        "general_settings": {"master_key": "os.environ/LITELLM_MASTER_KEY"},
    }
    (ROOT / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))

    groups = {}
    for entry in model_list:
        groups[entry["model_name"]] = groups.get(entry["model_name"], 0) + 1
    print(f"config.yaml: {len(model_list)} models " + ", ".join(f"{g}={n}" for g, n in groups.items()))
    print("keys in use: " + (", ".join(sorted(used)) or "none (no-key providers only)"), file=sys.stderr)


if __name__ == "__main__":
    main()
