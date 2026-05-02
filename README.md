# tg-supbot

A configurable Telegram support bot with a ticketing system, FAQ engine, and a JSON-driven menu architecture. Built to automate internal support workflows for multi-location retail operations — handles user verification, ticket lifecycle management, real-time admin-to-user chat, and broadcast announcements.

---

## Features

- **Phone-based user verification** — users authenticate via Telegram contact sharing, mapped against a permission config
- **Role-based access** — separate flows for `user` and `admin` roles, each with their own menu tree
- **Ticket system** — full lifecycle management: create, update, assign, close, with status tracking
- **Real-time texting** — bidirectional admin↔user chat within an active ticket context
- **FAQ engine** — regex-based NLP matches user input against a knowledge base and returns relevant instructions
- **JSON menu engine** — all UI text, buttons, and navigation is driven by a single JSON config with variable injection support
- **Admin panel** — live open ticket counter, announcement broadcasting to all verified users, ticket queue management
- **Async SQLite backend** — custom async database layer with WAL mode, write locking, and a singleton connection

---

## Architecture

```
tg-supbot/
├── main.py                  # Bot entrypoint, handler registration
├── bin/
│   ├── classes/
│   │   ├── aiodatabase.py   # Async SQLite layer (singleton, WAL, write lock)
│   │   ├── ticket_manager.py # Ticket dataclass + CRUD service layer
│   │   ├── auth.py          # Phone-based role verification
│   │   └── pattern_search.py # Regex FAQ engine
│   └── handlers/
│       ├── message_handlers.py   # Text message routing and state handlers
│       ├── callback_handlers.py  # Inline button handlers
│       ├── text_dispatch.py      # State router (maps menu_position → handler)
│       └── message_forwarding_handler.py # Admin↔user message relay
├── bot-data/
│   ├── messages.json        # All UI text, buttons, navigation (multilingual)
│   ├── config.json          # Bot token, supported languages, settings
│   └── users.json           # User permission map (phone → role, shop)
└── utils/
    ├── logger.py
    ├── paths.py
    └── config_loader.py
```

---

## How it works

### User flow
1. User sends any message → bot requests phone verification
2. Phone is matched against `users.json` → role and shop name assigned
3. User describes their problem → FAQ engine tries to match a known answer
4. If no match → ticket is created, admin is notified
5. Admin can open a direct chat channel with the user within the ticket context

### Menu engine
All bot messages and keyboards are defined in `messages.json`, keyed by `role → language → menu_position`. The `MessageConstructor` class loads the current state, injects dynamic variables (ticket ID, open ticket count, shop name, etc.), and renders the appropriate message and inline keyboard.

This means adding a new menu screen requires only a JSON entry — no code changes.

### Database layer
Custom async SQLite wrapper built on `aiosqlite`. Implements:
- Singleton pattern — one connection instance across the application
- Write lock via `asyncio.Lock` — prevents concurrent write conflicts
- WAL journal mode — better read/write concurrency
- Generic `insert`, `select`, `select_range`, `update` methods with parameterized queries

### Ticket states
| Status | Meaning |
|--------|---------|
| 1 | Open, unassigned |
| 2 | Assigned to department |
| 3 | In progress |
| 4 | Closed by user |
| 0 | Closed by admin |

---

## Setup

**Requirements:** Python 3.10+

```bash
# 1. Clone the repo
git clone https://github.com/dgessus/tg-supbot
cd tg-supbot

# 2. Create and activate virtualenv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r req.txt

# 4. Configure the bot
cp bot-data/config-template.json bot-data/config.json
# Edit config.json — add your bot token and settings

# 5. Configure users
cp bot-data/users-template.json bot-data/users.json
# Edit users.json — map phone numbers to roles and shop names

# 6. Run
python main.py
```

To run as a background service on Linux:
```bash
# systemd service or screen/tmux
screen -S supbot python main.py
```

---

## Configuration

### config.json
```json
{
  "bot_token": "YOUR_TOKEN_HERE",
  "supported_languages": ["uk", "en"],
  "cleanup_timeout": 300
}
```

### users.json
```json
{
  "+380991234567": {
    "role": "user",
    "shop_name": "Shop #12"
  },
  "+380997654321": {
    "role": "admin",
    "shop_name": null
  }
}
```

---

## Stack

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+
- [aiosqlite](https://github.com/omnilib/aiosqlite)
- Python 3.10+
