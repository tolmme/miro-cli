#!/usr/bin/env python3
"""Miro REST API v2 — direct urllib calls, zero dependencies.

Usage:
    python3 miro.py <command> '<json_args>'
    python3 miro.py <command> - <<'ARGS'
    {"key": "value"}
    ARGS

Auth (checked in order):
  1. MIRO_TOKEN env var
  2. macOS Keychain: service "miro-api-token" (or "miro-api-token-<account>")
  3. Config file: ~/.config/miro-cli/token (or ~/.config/miro-cli/token-<account>)

Multi-account:
  Pass "account" in JSON args to select a named account.
  Default account uses the base key/file; named accounts append "-<name>".
"""

import json, os, sys, subprocess, urllib.request, urllib.parse, urllib.error, platform

BASE = "https://api.miro.com/v2"

# ── Auth ──────────────────────────────────────────────────────────────────────

def _config_dir():
    """Return config directory, respecting platform conventions."""
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "miro-cli")
    return os.path.join(os.path.expanduser("~"), ".config", "miro-cli")

def _read_token_file(account=None):
    """Read token from config file."""
    fname = f"token-{account}" if account else "token"
    path = os.path.join(_config_dir(), fname)
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def _read_keychain(account=None):
    """Read token from macOS Keychain. Returns None on non-macOS or if not found."""
    if platform.system() != "Darwin":
        return None
    service = f"miro-api-token-{account}" if account else "miro-api-token"
    user = os.environ.get("USER", "")
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", user, "-s", service, "-w"],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except Exception:
        return None

def get_token(account=None):
    # 1. Env var (only for default account)
    t = os.environ.get("MIRO_TOKEN")
    if t and not account:
        return t.strip()

    # 2. macOS Keychain
    t = _read_keychain(account)
    if t:
        return t

    # 3. Config file
    t = _read_token_file(account)
    if t:
        return t

    # Nothing found — show platform-specific help
    if account:
        _die_no_token_named(account)
    else:
        _die_no_token()

def _die_no_token():
    lines = ["ERROR: No Miro API token found.", "", "Set up auth (pick one):"]
    lines.append(f"  1. Env var:    export MIRO_TOKEN=\"YOUR_TOKEN\"")
    if platform.system() == "Darwin":
        lines.append(f'  2. Keychain:   security add-generic-password -a "$USER" -s "miro-api-token" -w "YOUR_TOKEN"')
        lines.append(f"  3. Config:     echo YOUR_TOKEN > {_config_dir()}/token")
    else:
        lines.append(f"  2. Config:     echo YOUR_TOKEN > {_config_dir()}/token")
    lines.append("")
    lines.append("Get your token: Miro Settings > Your apps > Create new app > Install & copy token")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(1)

def _die_no_token_named(account):
    lines = [f"ERROR: No Miro token for account '{account}'.", "", "Set up auth (pick one):"]
    if platform.system() == "Darwin":
        lines.append(f'  1. Keychain:   security add-generic-password -a "$USER" -s "miro-api-token-{account}" -w "TOKEN"')
        lines.append(f"  2. Config:     echo TOKEN > {_config_dir()}/token-{account}")
    else:
        lines.append(f"  1. Config:     echo TOKEN > {_config_dir()}/token-{account}")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(1)

_TOKENS = {}

def token(account=None):
    if account not in _TOKENS:
        _TOKENS[account] = get_token(account)
    return _TOKENS[account]

# ── HTTP helper ───────────────────────────────────────────────────────────────

_ACTIVE_ACCOUNT = None

def api(method, path, body=None, query=None):
    url = f"{BASE}{path}"
    if query:
        url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token(_ACTIVE_ACCOUNT)}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        print(f"HTTP {e.code}: {body_err}", file=sys.stderr)
        sys.exit(1)

# ── Boards ────────────────────────────────────────────────────────────────────

def boards_list(args):
    """List boards accessible to the user."""
    return api("GET", "/boards", query={
        "limit": args.get("limit", 20),
        "sort": args.get("sort"),
        "query": args.get("query"),
        "team_id": args.get("team_id"),
        "project_id": args.get("project_id"),
    })

def boards_get(args):
    """Get board by ID."""
    return api("GET", f"/boards/{args['board_id']}")

def boards_create(args):
    """Create a new board."""
    body = {"name": args["name"]}
    if args.get("description"):
        body["description"] = args["description"]
    if args.get("team_id"):
        body["teamId"] = args["team_id"]
    if args.get("project_id"):
        body["projectId"] = args["project_id"]
    if args.get("policy"):
        body["policy"] = args["policy"]
    return api("POST", "/boards", body)

def boards_update(args):
    """Update board name/description."""
    body = {}
    if args.get("name"):
        body["name"] = args["name"]
    if args.get("description"):
        body["description"] = args["description"]
    return api("PATCH", f"/boards/{args['board_id']}", body)

def boards_delete(args):
    """Delete a board."""
    return api("DELETE", f"/boards/{args['board_id']}")

def boards_copy(args):
    """Copy a board."""
    body = {}
    if args.get("name"):
        body["name"] = args["name"]
    if args.get("team_id"):
        body["teamId"] = args["team_id"]
    return api("PUT", f"/boards/{args['board_id']}/copy", body)

# ── Board Members ─────────────────────────────────────────────────────────────

def members_list(args):
    """List board members."""
    return api("GET", f"/boards/{args['board_id']}/members", query={
        "limit": args.get("limit", 20),
        "offset": args.get("offset"),
    })

def members_share(args):
    """Share board with a user."""
    body = {"emails": args["emails"], "role": args.get("role", "commenter")}
    if args.get("message"):
        body["message"] = args["message"]
    return api("POST", f"/boards/{args['board_id']}/members", body)

def members_update(args):
    """Update member role on board."""
    return api("PATCH", f"/boards/{args['board_id']}/members/{args['member_id']}", {"role": args["role"]})

def members_remove(args):
    """Remove member from board."""
    return api("DELETE", f"/boards/{args['board_id']}/members/{args['member_id']}")

# ── Items (generic) ──────────────────────────────────────────────────────────

def items_list(args):
    """List all items on a board. Filter by type."""
    return api("GET", f"/boards/{args['board_id']}/items", query={
        "limit": args.get("limit", 50),
        "cursor": args.get("cursor"),
        "type": args.get("type"),
    })

def items_get(args):
    """Get a specific item."""
    return api("GET", f"/boards/{args['board_id']}/items/{args['item_id']}")

def items_update(args):
    """Update item position or parent."""
    body = {}
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("parent"):
        body["parent"] = args["parent"]
    return api("PATCH", f"/boards/{args['board_id']}/items/{args['item_id']}", body)

def items_delete(args):
    """Delete an item from board."""
    return api("DELETE", f"/boards/{args['board_id']}/items/{args['item_id']}")

# ── Sticky Notes ──────────────────────────────────────────────────────────────

def sticky_create(args):
    """Create a sticky note."""
    body = {"data": {"content": args["content"]}}
    if args.get("shape"):
        body["data"]["shape"] = args["shape"]
    style = {}
    if args.get("fill_color"):
        style["fillColor"] = args["fill_color"]
    if args.get("text_align"):
        style["textAlign"] = args["text_align"]
    if args.get("text_align_vertical"):
        style["textAlignVertical"] = args["text_align_vertical"]
    if style:
        body["style"] = style
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    if args.get("parent"):
        body["parent"] = args["parent"]
    return api("POST", f"/boards/{args['board_id']}/sticky_notes", body)

def sticky_get(args):
    """Get a sticky note."""
    return api("GET", f"/boards/{args['board_id']}/sticky_notes/{args['item_id']}")

def sticky_update(args):
    """Update a sticky note."""
    body = {}
    if args.get("content"):
        body["data"] = {"content": args["content"]}
        if args.get("shape"):
            body["data"]["shape"] = args["shape"]
    style = {}
    if args.get("fill_color"):
        style["fillColor"] = args["fill_color"]
    if args.get("text_align"):
        style["textAlign"] = args["text_align"]
    if style:
        body["style"] = style
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    return api("PATCH", f"/boards/{args['board_id']}/sticky_notes/{args['item_id']}", body)

def sticky_delete(args):
    """Delete a sticky note."""
    return api("DELETE", f"/boards/{args['board_id']}/sticky_notes/{args['item_id']}")

# ── Cards ─────────────────────────────────────────────────────────────────────

def card_create(args):
    """Create a card item."""
    body = {"data": {"title": args["title"]}}
    if args.get("description"):
        body["data"]["description"] = args["description"]
    if args.get("due_date"):
        body["data"]["dueDate"] = args["due_date"]
    if args.get("assignee_id"):
        body["data"]["assigneeId"] = args["assignee_id"]
    style = {}
    if args.get("card_theme"):
        style["cardTheme"] = args["card_theme"]
    if style:
        body["style"] = style
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    if args.get("parent"):
        body["parent"] = args["parent"]
    return api("POST", f"/boards/{args['board_id']}/cards", body)

def card_get(args):
    """Get a card item."""
    return api("GET", f"/boards/{args['board_id']}/cards/{args['item_id']}")

def card_update(args):
    """Update a card item."""
    body = {}
    data = {}
    if args.get("title"):
        data["title"] = args["title"]
    if args.get("description"):
        data["description"] = args["description"]
    if args.get("due_date"):
        data["dueDate"] = args["due_date"]
    if data:
        body["data"] = data
    if args.get("position"):
        body["position"] = args["position"]
    style = {}
    if args.get("card_theme"):
        style["cardTheme"] = args["card_theme"]
    if style:
        body["style"] = style
    return api("PATCH", f"/boards/{args['board_id']}/cards/{args['item_id']}", body)

def card_delete(args):
    """Delete a card item."""
    return api("DELETE", f"/boards/{args['board_id']}/cards/{args['item_id']}")

# ── Shapes ────────────────────────────────────────────────────────────────────

def shape_create(args):
    """Create a shape item."""
    body = {"data": {"shape": args.get("shape", "rectangle")}}
    if args.get("content"):
        body["data"]["content"] = args["content"]
    style = {}
    for k in ["fillColor", "fillOpacity", "fontFamily", "fontSize", "textAlign", "textAlignVertical",
              "borderColor", "borderWidth", "borderOpacity", "borderStyle", "color"]:
        snake = "".join(f"_{c.lower()}" if c.isupper() else c for c in k).lstrip("_")
        if args.get(snake):
            style[k] = args[snake]
        elif args.get(k):
            style[k] = args[k]
    if style:
        body["style"] = style
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    if args.get("parent"):
        body["parent"] = args["parent"]
    return api("POST", f"/boards/{args['board_id']}/shapes", body)

def shape_get(args):
    """Get a shape."""
    return api("GET", f"/boards/{args['board_id']}/shapes/{args['item_id']}")

def shape_update(args):
    """Update a shape."""
    body = {}
    data = {}
    if args.get("content"):
        data["content"] = args["content"]
    if args.get("shape"):
        data["shape"] = args["shape"]
    if data:
        body["data"] = data
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    return api("PATCH", f"/boards/{args['board_id']}/shapes/{args['item_id']}", body)

def shape_delete(args):
    """Delete a shape."""
    return api("DELETE", f"/boards/{args['board_id']}/shapes/{args['item_id']}")

# ── Text Items ────────────────────────────────────────────────────────────────

def text_create(args):
    """Create a text item."""
    body = {"data": {"content": args["content"]}}
    style = {}
    if args.get("fill_color"):
        style["fillColor"] = args["fill_color"]
    if args.get("font_size"):
        style["fontSize"] = args["font_size"]
    if args.get("text_align"):
        style["textAlign"] = args["text_align"]
    if args.get("color"):
        style["color"] = args["color"]
    if style:
        body["style"] = style
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    if args.get("parent"):
        body["parent"] = args["parent"]
    return api("POST", f"/boards/{args['board_id']}/texts", body)

def text_get(args):
    """Get a text item."""
    return api("GET", f"/boards/{args['board_id']}/texts/{args['item_id']}")

def text_update(args):
    """Update a text item."""
    body = {}
    if args.get("content"):
        body["data"] = {"content": args["content"]}
    if args.get("position"):
        body["position"] = args["position"]
    style = {}
    if args.get("fill_color"):
        style["fillColor"] = args["fill_color"]
    if args.get("font_size"):
        style["fontSize"] = args["font_size"]
    if style:
        body["style"] = style
    return api("PATCH", f"/boards/{args['board_id']}/texts/{args['item_id']}", body)

def text_delete(args):
    """Delete a text item."""
    return api("DELETE", f"/boards/{args['board_id']}/texts/{args['item_id']}")

# ── Connectors ────────────────────────────────────────────────────────────────

def connector_create(args):
    """Create a connector between two items."""
    body = {}
    if args.get("start_item"):
        body["startItem"] = args["start_item"]
    if args.get("end_item"):
        body["endItem"] = args["end_item"]
    if args.get("shape"):
        body["shape"] = args["shape"]
    if args.get("captions"):
        body["captions"] = args["captions"]
    style = {}
    for k in ["strokeColor", "strokeWidth", "strokeStyle", "startStrokeCap", "endStrokeCap",
              "fontSize", "color", "textOrientation"]:
        snake = "".join(f"_{c.lower()}" if c.isupper() else c for c in k).lstrip("_")
        if args.get(snake):
            style[k] = args[snake]
        elif args.get(k):
            style[k] = args[k]
    if style:
        body["style"] = style
    return api("POST", f"/boards/{args['board_id']}/connectors", body)

def connector_get(args):
    """Get a connector."""
    return api("GET", f"/boards/{args['board_id']}/connectors/{args['connector_id']}")

def connector_update(args):
    """Update a connector."""
    body = {}
    if args.get("start_item"):
        body["startItem"] = args["start_item"]
    if args.get("end_item"):
        body["endItem"] = args["end_item"]
    if args.get("shape"):
        body["shape"] = args["shape"]
    if args.get("captions"):
        body["captions"] = args["captions"]
    style = {}
    for k in ["strokeColor", "strokeWidth", "strokeStyle", "startStrokeCap", "endStrokeCap"]:
        snake = "".join(f"_{c.lower()}" if c.isupper() else c for c in k).lstrip("_")
        if args.get(snake):
            style[k] = args[snake]
    if style:
        body["style"] = style
    return api("PATCH", f"/boards/{args['board_id']}/connectors/{args['connector_id']}", body)

def connector_delete(args):
    """Delete a connector."""
    return api("DELETE", f"/boards/{args['board_id']}/connectors/{args['connector_id']}")

def connectors_list(args):
    """List all connectors on a board."""
    return api("GET", f"/boards/{args['board_id']}/connectors", query={
        "limit": args.get("limit", 50),
        "cursor": args.get("cursor"),
    })

# ── Frames ────────────────────────────────────────────────────────────────────

def frame_create(args):
    """Create a frame."""
    body = {"data": {"title": args.get("title", ""), "format": args.get("format", "custom")}}
    if args.get("type"):
        body["data"]["type"] = args["type"]
    style = {}
    if args.get("fill_color"):
        style["fillColor"] = args["fill_color"]
    if style:
        body["style"] = style
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    return api("POST", f"/boards/{args['board_id']}/frames", body)

def frame_get(args):
    """Get a frame."""
    return api("GET", f"/boards/{args['board_id']}/frames/{args['item_id']}")

def frame_items(args):
    """Get items inside a frame."""
    return api("GET", f"/boards/{args['board_id']}/items", query={
        "parent_item_id": args["item_id"],
        "limit": args.get("limit", 50),
        "cursor": args.get("cursor"),
        "type": args.get("type"),
    })

def frame_update(args):
    """Update a frame."""
    body = {}
    data = {}
    if args.get("title"):
        data["title"] = args["title"]
    if args.get("format"):
        data["format"] = args["format"]
    if data:
        body["data"] = data
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    return api("PATCH", f"/boards/{args['board_id']}/frames/{args['item_id']}", body)

def frame_delete(args):
    """Delete a frame."""
    return api("DELETE", f"/boards/{args['board_id']}/frames/{args['item_id']}")

# ── Images ────────────────────────────────────────────────────────────────────

def image_create(args):
    """Create an image item from URL."""
    body = {"data": {"url": args["url"]}}
    if args.get("title"):
        body["data"]["title"] = args["title"]
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    if args.get("parent"):
        body["parent"] = args["parent"]
    return api("POST", f"/boards/{args['board_id']}/images", body)

def image_get(args):
    """Get an image item."""
    return api("GET", f"/boards/{args['board_id']}/images/{args['item_id']}")

def image_update(args):
    """Update an image item."""
    body = {}
    if args.get("title"):
        body["data"] = {"title": args["title"]}
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    return api("PATCH", f"/boards/{args['board_id']}/images/{args['item_id']}", body)

def image_delete(args):
    """Delete an image item."""
    return api("DELETE", f"/boards/{args['board_id']}/images/{args['item_id']}")

# ── Embeds ────────────────────────────────────────────────────────────────────

def embed_create(args):
    """Create an embed item from URL."""
    body = {"data": {"url": args["url"]}}
    if args.get("mode"):
        body["data"]["mode"] = args["mode"]
    if args.get("preview_url"):
        body["data"]["previewUrl"] = args["preview_url"]
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    if args.get("parent"):
        body["parent"] = args["parent"]
    return api("POST", f"/boards/{args['board_id']}/embeds", body)

def embed_get(args):
    """Get an embed item."""
    return api("GET", f"/boards/{args['board_id']}/embeds/{args['item_id']}")

# ── Tags ──────────────────────────────────────────────────────────────────────

def tag_create(args):
    """Create a tag on a board."""
    body = {"title": args["title"]}
    if args.get("fill_color"):
        body["fillColor"] = args["fill_color"]
    return api("POST", f"/boards/{args['board_id']}/tags", body)

def tag_get(args):
    """Get a tag."""
    return api("GET", f"/boards/{args['board_id']}/tags/{args['tag_id']}")

def tags_list(args):
    """List tags on a board."""
    return api("GET", f"/boards/{args['board_id']}/tags", query={
        "limit": args.get("limit", 50),
        "offset": args.get("offset"),
    })

def tag_update(args):
    """Update a tag."""
    body = {}
    if args.get("title"):
        body["title"] = args["title"]
    if args.get("fill_color"):
        body["fillColor"] = args["fill_color"]
    return api("PATCH", f"/boards/{args['board_id']}/tags/{args['tag_id']}", body)

def tag_delete(args):
    """Delete a tag."""
    return api("DELETE", f"/boards/{args['board_id']}/tags/{args['tag_id']}")

def tag_attach(args):
    """Attach a tag to an item."""
    body = {"tagId": args["tag_id"]}
    return api("POST", f"/boards/{args['board_id']}/items/{args['item_id']}/tags", body)

def tag_detach(args):
    """Detach a tag from an item."""
    return api("DELETE", f"/boards/{args['board_id']}/items/{args['item_id']}/tags/{args['tag_id']}")

def item_tags(args):
    """Get tags attached to an item."""
    return api("GET", f"/boards/{args['board_id']}/items/{args['item_id']}/tags")

# ── Groups ────────────────────────────────────────────────────────────────────

def group_create(args):
    """Create a group from items."""
    return api("POST", f"/boards/{args['board_id']}/groups", {"items": args["items"]})

def groups_list(args):
    """List groups on a board."""
    return api("GET", f"/boards/{args['board_id']}/groups", query={
        "limit": args.get("limit", 50),
        "cursor": args.get("cursor"),
    })

def group_get(args):
    """Get a group."""
    return api("GET", f"/boards/{args['board_id']}/groups/{args['group_id']}")

def group_items(args):
    """Get items in a group."""
    return api("GET", f"/boards/{args['board_id']}/groups/{args['group_id']}/items", query={
        "limit": args.get("limit", 50),
        "cursor": args.get("cursor"),
    })

def group_update(args):
    """Update a group (add/remove items)."""
    body = {}
    if args.get("items"):
        body["items"] = args["items"]
    return api("PUT", f"/boards/{args['board_id']}/groups/{args['group_id']}", body)

def group_delete(args):
    """Delete (ungroup) a group."""
    return api("DELETE", f"/boards/{args['board_id']}/groups/{args['group_id']}")

# ── Documents ─────────────────────────────────────────────────────────────────

def document_create(args):
    """Create a document item from URL."""
    body = {"data": {"url": args["url"]}}
    if args.get("title"):
        body["data"]["title"] = args["title"]
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    if args.get("parent"):
        body["parent"] = args["parent"]
    return api("POST", f"/boards/{args['board_id']}/documents", body)

def document_get(args):
    """Get a document item."""
    return api("GET", f"/boards/{args['board_id']}/documents/{args['item_id']}")

# ── App Cards ─────────────────────────────────────────────────────────────────

def app_card_create(args):
    """Create an app card."""
    body = {"data": {"title": args["title"]}}
    if args.get("description"):
        body["data"]["description"] = args["description"]
    if args.get("status"):
        body["data"]["status"] = args["status"]
    if args.get("fields"):
        body["data"]["fields"] = args["fields"]
    if args.get("position"):
        body["position"] = args["position"]
    if args.get("geometry"):
        body["geometry"] = args["geometry"]
    style = {}
    if args.get("card_theme"):
        style["cardTheme"] = args["card_theme"]
    if style:
        body["style"] = style
    return api("POST", f"/boards/{args['board_id']}/app_cards", body)

def app_card_get(args):
    """Get an app card."""
    return api("GET", f"/boards/{args['board_id']}/app_cards/{args['item_id']}")

def app_card_update(args):
    """Update an app card."""
    body = {}
    data = {}
    if args.get("title"):
        data["title"] = args["title"]
    if args.get("description"):
        data["description"] = args["description"]
    if args.get("status"):
        data["status"] = args["status"]
    if args.get("fields"):
        data["fields"] = args["fields"]
    if data:
        body["data"] = data
    if args.get("position"):
        body["position"] = args["position"]
    return api("PATCH", f"/boards/{args['board_id']}/app_cards/{args['item_id']}", body)

def app_card_delete(args):
    """Delete an app card."""
    return api("DELETE", f"/boards/{args['board_id']}/app_cards/{args['item_id']}")

# ── CLI dispatch ──────────────────────────────────────────────────────────────

TOOLS = {
    "boards_list": boards_list, "boards_get": boards_get, "boards_create": boards_create,
    "boards_update": boards_update, "boards_delete": boards_delete, "boards_copy": boards_copy,
    "members_list": members_list, "members_share": members_share,
    "members_update": members_update, "members_remove": members_remove,
    "items_list": items_list, "items_get": items_get, "items_update": items_update, "items_delete": items_delete,
    "sticky_create": sticky_create, "sticky_get": sticky_get, "sticky_update": sticky_update, "sticky_delete": sticky_delete,
    "card_create": card_create, "card_get": card_get, "card_update": card_update, "card_delete": card_delete,
    "shape_create": shape_create, "shape_get": shape_get, "shape_update": shape_update, "shape_delete": shape_delete,
    "text_create": text_create, "text_get": text_get, "text_update": text_update, "text_delete": text_delete,
    "connector_create": connector_create, "connector_get": connector_get, "connector_update": connector_update,
    "connector_delete": connector_delete, "connectors_list": connectors_list,
    "frame_create": frame_create, "frame_get": frame_get, "frame_items": frame_items,
    "frame_update": frame_update, "frame_delete": frame_delete,
    "image_create": image_create, "image_get": image_get, "image_update": image_update, "image_delete": image_delete,
    "embed_create": embed_create, "embed_get": embed_get,
    "tag_create": tag_create, "tag_get": tag_get, "tags_list": tags_list,
    "tag_update": tag_update, "tag_delete": tag_delete, "tag_attach": tag_attach,
    "tag_detach": tag_detach, "item_tags": item_tags,
    "group_create": group_create, "groups_list": groups_list, "group_get": group_get,
    "group_items": group_items, "group_update": group_update, "group_delete": group_delete,
    "document_create": document_create, "document_get": document_get,
    "app_card_create": app_card_create, "app_card_get": app_card_get,
    "app_card_update": app_card_update, "app_card_delete": app_card_delete,
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: miro.py <command> [json_args | - (stdin)]")
        print(f"\nCommands ({len(TOOLS)}):")
        for name, fn in TOOLS.items():
            print(f"  {name:24s} {fn.__doc__ or ''}")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in TOOLS:
        print(f"Unknown command: {cmd}\nRun with --help to see all commands.", file=sys.stderr)
        sys.exit(1)

    args = {}
    if len(sys.argv) > 2:
        raw = sys.argv[2]
        if raw == "-":
            raw = sys.stdin.read()
        try:
            args = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)

    global _ACTIVE_ACCOUNT
    _ACTIVE_ACCOUNT = args.pop("account", None)

    result = TOOLS[cmd](args)
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
