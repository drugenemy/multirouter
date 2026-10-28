# multirouter

Claude Code on free AI models. One small router on your computer stacks many free
providers. When one hits its limit, the next one answers. You get a new command,
`claude-free`. Your normal `claude` and your paid plan are not touched.

By Sardor Nurmurodov.

## Install: paste this into Claude Code

```
Set up multirouter for me. Clone https://github.com/drugenemy/multirouter into
~/multirouter, then open SETUP.md in it and follow it step by step.
```

Claude Code runs the installer, walks you through getting free keys one by one,
tests every model, and tells you how to start. Works on macOS and Linux (Windows: use WSL).

## What you get

- `claude-free`: Claude Code on a stack of up to 23 free models
- Automatic switching: when a provider says "limit reached", the next one takes over
- A token bar above the prompt:

```
memory ████████░░░░░░░░░░░░ 40% · 51.2K of 128.0K
today  ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱ ~140M of ~155M tokens left
✧ 1.23M tokens conjured from thin air · this session 45.2K
```

  - **memory**: how full this chat is before Claude Code shrinks it
  - **today**: estimated free tokens left today, all providers together
  - **total**: all-time tokens, with a phrase and color that change every 4 seconds

## Model groups

Claude Code asks for three kinds of model. Each is a stack, tried top first:

| Group | Used for | Stack |
|---|---|---|
| best | main work | Kimi K2.6, GLM-5.3 (NVIDIA) → Nemotron Ultra 550B (NVIDIA, OpenRouter) → Kilo, Mistral Medium |
| good | when best is used up | DeepSeek V4.1 Flash, MiniMax M3.1, GLM-5.3 Flash (NVIDIA) → Gemini 3.5 Flash, GLM-4.7 and 4.5 Flash (Z.ai) → Gemma 4, OpenRouter free, Codestral → Kilo auto, LLM7 MiniMax |
| fast | small background jobs | gpt-oss-120b, Qwen 3.8 (Groq), Nemotron Lightning (NVIDIA) → Gemini Flash Lite → LLM7 |

The list lives in `build_config.py`. Free model names change often; SETUP.md tells
Claude how to refresh them.

## Free keys

It works with no keys at all (Kilo and LLM7), just slower. Each key adds a stack.
One account per provider: making many accounts to get more free quota breaks their terms.

| Key | Sign up | Free amount | Notes |
|---|---|---|---|
| NVIDIA_API_KEY | https://build.nvidia.com | about 40 a minute per model | The best one: Kimi, GLM, DeepSeek, MiniMax. Needs phone check; if your country is missing, email help@build.nvidia.com |
| OPENROUTER_API_KEY | https://openrouter.ai/keys | 50 requests a day; 1,000 after a one-time $10 top-up | Best value for $10 |
| GROQ_API_KEY | https://console.groq.com/keys | about 1,000 a day per model | Very fast |
| GEMINI_API_KEY | https://aistudio.google.com/apikey | changes per model | |
| ZAI_API_KEY | https://z.ai/manage-apikey/apikey-list | one request at a time | GLM Flash |
| LLM7_API_KEY | https://token.llm7.io | optional | Works without a key; a key raises the limit |
| MISTRAL_API_KEY | https://console.mistral.ai/api-keys | not free anymore | Optional. Their $11.99 Pro plan includes $30 a month of API credits |

Not used, on purpose: OpenCode Zen (free models only work in their own app),
ModelScope and SiliconFlow (need a Chinese ID), Cerebras and GitHub Models (no longer
free), Cloudflare, Cohere, Hugging Face, OVH (too small).

## Commands

```
claude-free            open Claude Code on free models, in the current folder
claude-free check      test every model once (run after adding keys)
claude-free status     list the models the router has
claude-free restart    after editing .env
claude-free stop       stop the router
```

## Privacy, read this

- Free providers may keep and train on what you send. Use claude-free for personal
  and open projects, not for work or private data.
- Run it inside a project folder, never in your home folder or Desktop: from there it
  can read everything below.
- Your main `~/.claude/CLAUDE.md` would load into every claude-free session (Claude
  Code reads it as a parent-folder file). The installer blocks it with
  `claudeMdExcludes` in `~/.claude-free/settings.json`. Add any other private folders there.
- Keys live only in `.env` (only you can read it). They go to the router, never to
  Claude Code.

## How it works

- `bin/claude-free` starts a [LiteLLM](https://github.com/BerriAI/litellm) router on
  `127.0.0.1:4520` (change it with `MULTIROUTER_PORT`) and runs Claude Code against it,
  with its own settings folder (`~/.claude-free`).
- `build_config.py` writes the router's `config.yaml` from `.env`, keeping only providers
  you have keys for.
- `usage_logger.py` counts what each provider used today (`logs/usage.json`) for the bar.
  "Left" is an estimate: daily limits times your average request size.
- `mods/free-token-counter` is a Claude Code mod that draws the bar
  (needs Claude Code 2.1.308 or newer).

## License

MIT
