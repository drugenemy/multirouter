#!/usr/bin/env bash
# One-time setup for multirouter. Safe to run again.
#
#   ./install.sh
#
# What it does:
#   1. makes a Python environment in .venv and installs the LiteLLM router
#   2. creates .env from .env.example (you paste your own keys there later)
#   3. links the `claude-free` command into ~/.local/bin
#   4. keeps your main ~/.claude/CLAUDE.md out of claude-free sessions
#   5. checks your Claude Code version
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${MULTIROUTER_BIN_DIR:-$HOME/.local/bin}"
FREE_CONFIG="$HOME/.claude-free"
LITELLM_VERSION="1.106.5"
MIN_CLAUDE="2.1.308"

say() { printf '\n==> %s\n' "$*"; }
cd "$ROOT"

say "Python environment and LiteLLM $LITELLM_VERSION"
if command -v uv >/dev/null 2>&1; then
  [ -x .venv/bin/python ] || uv venv --python 3.12 .venv -q
  uv pip install --python .venv/bin/python -q "litellm[proxy]==$LITELLM_VERSION" httpx pyyaml
elif command -v python3 >/dev/null 2>&1; then
  if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    echo "Need Python 3.10 or newer (found $(python3 --version)). Or install uv: https://docs.astral.sh/uv/" >&2
    exit 1
  fi
  # a half-made .venv (no pip inside) is rebuilt instead of failing on every run
  if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    rm -rf .venv
    if ! python3 -m venv .venv; then
      echo "python3 cannot make a venv. On Debian/Ubuntu: sudo apt install python3-venv" >&2
      exit 1
    fi
  fi
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q "litellm[proxy]==$LITELLM_VERSION" httpx pyyaml
else
  echo "Need uv (https://docs.astral.sh/uv/) or python3 3.10+. Install one, then run again." >&2
  exit 1
fi

say "Keys file"
mkdir -p logs
if [ -f .env ]; then
  echo ".env already exists, left as it is."
else
  cp .env.example .env
  chmod 600 .env
  echo "Created .env (only you can read it). Paste your keys there."
fi

say "claude-free command"
mkdir -p "$BIN_DIR"
chmod +x bin/claude-free
ln -sf "$ROOT/bin/claude-free" "$BIN_DIR/claude-free"
echo "Linked $BIN_DIR/claude-free"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "NOTE: $BIN_DIR is not on your PATH. Add this line to ~/.zshrc or ~/.bashrc:"
     echo "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

say "Privacy: keep your main Claude instructions out of the free models"
# Claude Code reads ~/.claude/CLAUDE.md as a parent-folder file in every project under
# your home folder, even with a separate settings folder. Free providers may keep what
# they see, so claude-free skips it.
mkdir -p "$FREE_CONFIG"
.venv/bin/python - "$FREE_CONFIG/settings.json" "$HOME/.claude/**" <<'EOF'
import json, sys
from pathlib import Path
path, pattern = Path(sys.argv[1]), sys.argv[2]
try:
    settings = json.loads(path.read_text()) if path.exists() else {}
except ValueError:
    sys.exit(f"{path} is not valid JSON. Fix it, then run ./install.sh again.")
excludes = settings.setdefault("claudeMdExcludes", [])
if not isinstance(excludes, list):
    sys.exit(f"claudeMdExcludes in {path} must be a list. Fix it, then run ./install.sh again.")
if pattern not in excludes:
    excludes.append(pattern)
path.write_text(json.dumps(settings, indent=2) + "\n")
print(f"{path}: claudeMdExcludes = {excludes}")
EOF

say "Claude Code version"
if ! command -v claude >/dev/null 2>&1; then
  echo "Claude Code is not installed: https://code.claude.com/docs/en/setup" >&2
  exit 1
fi
have="$(claude --version | awk '{print $1}')"
if .venv/bin/python -c "import re, sys; a, b = ([int(x) for x in re.findall(r'\d+', v)[:3]] for v in sys.argv[1:]); sys.exit(a < b)" "$have" "$MIN_CLAUDE"; then
  echo "Claude Code $have is fine."
else
  echo "Claude Code $have is older than $MIN_CLAUDE (needed for the token bar). Run: claude update"
fi

say "Done"
cat <<EOF
Next:
  1. Get free keys and paste them into $ROOT/.env (links in README.md).
     It already works with no keys at all, just slower.
  2. Test every model:   claude-free check
  3. Use it:             cd <your project> && claude-free
EOF
