#!/usr/bin/env python3
"""One-command installer for miro-cli Claude Code skill.

Usage:
    python3 install.py YOUR_MIRO_TOKEN
    python3 install.py YOUR_MIRO_TOKEN --account alma
"""

import os, sys, platform, urllib.request, json

MIRO_PY_URL = "https://raw.githubusercontent.com/tolmme/miro-cli/main/miro.py"

def home():
    return os.path.expanduser("~")

def skill_dir():
    return os.path.join(home(), ".claude", "skills", "miro")

def scripts_dir():
    return os.path.join(skill_dir(), "scripts")

def miro_py_path():
    return os.path.join(scripts_dir(), "miro.py")

def config_dir():
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", home())
        return os.path.join(base, "miro-cli")
    return os.path.join(home(), ".config", "miro-cli")

def save_token(token, account=None):
    d = config_dir()
    os.makedirs(d, exist_ok=True)
    fname = f"token-{account}" if account else "token"
    path = os.path.join(d, fname)
    with open(path, "w") as f:
        f.write(token.strip() + "\n")
    if platform.system() != "Windows":
        os.chmod(path, 0o600)
    print(f"  Token saved to {path}")

def download_miro_py():
    d = scripts_dir()
    os.makedirs(d, exist_ok=True)
    path = miro_py_path()
    print(f"  Downloading miro.py ...")
    urllib.request.urlretrieve(MIRO_PY_URL, path)
    if platform.system() != "Windows":
        os.chmod(path, 0o755)
    print(f"  Saved to {path}")

def create_skill_md():
    path = os.path.join(skill_dir(), "SKILL.md")
    py = miro_py_path()
    # Use forward slashes even on Windows for the skill definition
    py_escaped = py.replace("\\", "/")
    content = f"""---
name: miro
description: "Miro board automation via REST API v2. Create/manage boards, sticky notes, shapes, cards, connectors, frames, tags, images. Use for ANY Miro task."
allowed-tools: Bash(python3 {py_escaped} *)
---

# Miro

Direct REST API v2 calls. Zero dependencies.

## Calling pattern

```bash
python3 {py_escaped} <command> '<json_args>'
python3 {py_escaped} boards_list '{{}}'
python3 {py_escaped} sticky_create '{{"board_id":"ID","content":"Hello","fill_color":"light_yellow","position":{{"x":0,"y":0}}}}'
```

All 65 commands: `python3 {py_escaped} --help`
"""
    with open(path, "w") as f:
        f.write(content)
    print(f"  Skill created at {path}")

def verify(account=None):
    """Quick API call to verify the token works."""
    py = miro_py_path()
    import subprocess
    args_json = json.dumps({"account": account, "limit": 1}) if account else '{"limit":1}'
    try:
        r = subprocess.run(
            [sys.executable, py, "boards_list", args_json],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            total = data.get("total", len(data.get("data", [])))
            print(f"  Token works! You have access to {total} board(s).")
            return True
        else:
            print(f"  WARNING: Token check failed: {r.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  WARNING: Could not verify token: {e}")
        return False

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 install.py YOUR_MIRO_TOKEN [--account NAME]")
        print()
        print("Installs miro-cli as a Claude Code skill:")
        print("  1. Downloads miro.py")
        print("  2. Saves your API token")
        print("  3. Creates Claude Code skill definition")
        print()
        print("Get your token: Miro Settings > Your apps > Create new app > Install & copy token")
        print("Or ask your team lead for the shared token.")
        sys.exit(0)

    token = sys.argv[1]
    account = None
    if "--account" in sys.argv:
        idx = sys.argv.index("--account")
        if idx + 1 < len(sys.argv):
            account = sys.argv[idx + 1]

    print("Installing miro-cli skill...")
    print()

    download_miro_py()
    save_token(token, account)
    create_skill_md()

    print()
    print("Verifying...")
    verify(account)

    print()
    print("Done! Restart Claude Code to pick up the new skill.")
    print("Try: ask Claude to \"list my Miro boards\"")

if __name__ == "__main__":
    main()
