# miro-cli

Single-file Miro REST API v2 client. Zero dependencies. Python 3.7+.

65 commands covering boards, sticky notes, shapes, cards, connectors, frames, text, images, embeds, tags, groups, documents, and app cards.

## Install (one command)

Get the token from your team lead, then run:

```bash
# macOS / Linux
python3 <(curl -s https://raw.githubusercontent.com/tolmme/miro-cli/main/install.py) YOUR_TOKEN

# Windows (PowerShell)
curl -o install.py https://raw.githubusercontent.com/tolmme/miro-cli/main/install.py; python install.py YOUR_TOKEN; del install.py
```

This downloads `miro.py`, saves the token, and creates the Claude Code skill. Restart Claude Code and you're done.

## Manual Installation

If you prefer to set things up yourself:

```bash
# 1. Download
curl -O https://raw.githubusercontent.com/tolmme/miro-cli/main/miro.py

# 2. Save token
export MIRO_TOKEN="your-token-here"

# 3. Use it
python3 miro.py boards_list '{}'
```

No `pip install` needed. Uses only Python standard library.

## Authentication

Token is resolved in this order:

| Priority | Method | Works on | Setup |
|----------|--------|----------|-------|
| 1 | `MIRO_TOKEN` env var | All OS | `export MIRO_TOKEN="token"` |
| 2 | macOS Keychain | macOS | `security add-generic-password -a "$USER" -s "miro-api-token" -w "token"` |
| 3 | Config file | All OS | `echo "token" > ~/.config/miro-cli/token` |

On Windows, the config file path is `%APPDATA%\miro-cli\token`.

### Getting Your API Token

1. Open [Miro App Settings](https://miro.com/app/settings/user-profile/apps)
2. Click **Create new app**
3. Set permissions: `boards:read`, `boards:write`
4. Click **Install app and get OAuth token** on your team
5. Copy the access token

For small teams, one person can create the token and share it with the team. Everyone uses the same `MIRO_TOKEN`. For larger organizations, each user should create their own app and token.

### Multiple Accounts

You can manage tokens for different Miro teams/accounts:

```bash
# Default account
export MIRO_TOKEN="token-for-default"

# Named accounts via config files
mkdir -p ~/.config/miro-cli
echo "token-for-work" > ~/.config/miro-cli/token-work
echo "token-for-client" > ~/.config/miro-cli/token-client

# macOS Keychain (alternative)
security add-generic-password -a "$USER" -s "miro-api-token-work" -w "token-for-work"

# Use named account by passing "account" in args
python3 miro.py boards_list '{"account":"work"}'
python3 miro.py boards_list '{"account":"client"}'
```

## Usage

```bash
python3 miro.py <command> '<json_args>'

# Or pipe JSON via stdin
echo '{"board_id":"abc123"}' | python3 miro.py boards_get -

# Heredoc for complex args
python3 miro.py shape_create - <<'ARGS'
{
  "board_id": "abc123",
  "shape": "round_rectangle",
  "content": "<b>Title</b><br>Description",
  "fillColor": "#e6f3ff",
  "position": {"x": 100, "y": 200},
  "geometry": {"width": 300, "height": 150}
}
ARGS
```

## All 65 Commands

**Boards (6):** `boards_list`, `boards_get`, `boards_create`, `boards_update`, `boards_delete`, `boards_copy`

**Members (4):** `members_list`, `members_share`, `members_update`, `members_remove`

**Items (4):** `items_list`, `items_get`, `items_update`, `items_delete`

**Sticky Notes (4):** `sticky_create`, `sticky_get`, `sticky_update`, `sticky_delete`

**Cards (4):** `card_create`, `card_get`, `card_update`, `card_delete`

**Shapes (4):** `shape_create`, `shape_get`, `shape_update`, `shape_delete`

**Text (4):** `text_create`, `text_get`, `text_update`, `text_delete`

**Connectors (5):** `connector_create`, `connector_get`, `connector_update`, `connector_delete`, `connectors_list`

**Frames (5):** `frame_create`, `frame_get`, `frame_items`, `frame_update`, `frame_delete`

**Images (4):** `image_create`, `image_get`, `image_update`, `image_delete`

**Embeds (2):** `embed_create`, `embed_get`

**Tags (8):** `tag_create`, `tag_get`, `tags_list`, `tag_update`, `tag_delete`, `tag_attach`, `tag_detach`, `item_tags`

**Groups (6):** `group_create`, `groups_list`, `group_get`, `group_items`, `group_update`, `group_delete`

**Documents (2):** `document_create`, `document_get`

**App Cards (4):** `app_card_create`, `app_card_get`, `app_card_update`, `app_card_delete`

Run `python3 miro.py --help` for the full list with descriptions.

## Examples

### Create a sticky note

```bash
python3 miro.py sticky_create '{
  "board_id": "abc123",
  "content": "Remember to review PR",
  "fill_color": "yellow",
  "position": {"x": 0, "y": 0}
}'
```

### Create a frame with items inside

```bash
# Create frame
FRAME=$(python3 miro.py frame_create '{
  "board_id": "abc123",
  "title": "Sprint Board",
  "position": {"x": 0, "y": 0},
  "geometry": {"width": 1200, "height": 800}
}' | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Add items to frame
python3 miro.py sticky_create "{
  \"board_id\": \"abc123\",
  \"content\": \"Task 1\",
  \"fill_color\": \"light_green\",
  \"parent\": {\"id\": \"$FRAME\"},
  \"position\": {\"x\": 100, \"y\": 100}
}"
```

### Connect two items

```bash
python3 miro.py connector_create '{
  "board_id": "abc123",
  "start_item": {"id": "item1", "snapTo": "right"},
  "end_item": {"id": "item2", "snapTo": "left"},
  "shape": "elbowed",
  "strokeColor": "#ff0000"
}'
```

### List and filter items

```bash
# List all frames
python3 miro.py items_list '{"board_id": "abc123", "type": "frame"}'

# Get items inside a frame
python3 miro.py frame_items '{"board_id": "abc123", "item_id": "frame_id"}'
```

### Share a board

```bash
python3 miro.py members_share '{
  "board_id": "abc123",
  "emails": ["alice@example.com", "bob@example.com"],
  "role": "editor",
  "message": "Join our project board!"
}'
```

## Claude Code Skill

To use as a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill, create `~/.claude/skills/miro/SKILL.md`:

```yaml
---
name: miro
description: "Miro board automation via REST API v2."
allowed-tools: Bash(python3 /path/to/miro.py *)
---

# Miro

python3 /path/to/miro.py <command> '<json_args>'
```

Replace `/path/to/miro.py` with the actual path where you saved the script.

## Parameter Reference

### Position

```json
{"x": 100, "y": 200, "origin": "center"}
```

When placing items inside a frame (using `parent`), coordinates are **relative to the frame's top-left corner**.

### Geometry

```json
{"width": 300, "height": 200}
```

### Parent (place inside frame)

```json
{"id": "frame_item_id"}
```

### Shapes

Available shapes for `shape_create`: `rectangle`, `circle`, `triangle`, `wedge_round_rectangle_callout`, `round_rectangle`, `rhombus`, `parallelogram`, `trapezoid`, `pentagon`, `hexagon`, `octagon`, `star`, and various `flow_chart_*` shapes.

### Sticky note colors

`gray`, `light_yellow`, `yellow`, `orange`, `light_green`, `green`, `dark_green`, `cyan`, `light_pink`, `pink`, `violet`, `red`, `light_blue`, `blue`, `dark_blue`, `black`

### Tag colors

`red`, `light_green`, `cyan`, `yellow`, `magenta`, `green`, `blue`, `gray`, `violet`, `dark_green`, `dark_blue`, `black`

### Connector snap points

`auto`, `top`, `bottom`, `left`, `right`

### Connector stroke caps

`none`, `stealth`, `diamond`, `diamond_filled`, `oval`, `oval_filled`, `arrow`, `triangle`, `triangle_filled`, `erd_one`, `erd_many`, `erd_one_or_many`, `erd_only_one`, `erd_zero_or_one`, `erd_zero_or_many`

## License

MIT
