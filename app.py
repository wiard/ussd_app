from __future__ import annotations

from ussd_warnings import *

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from flask import Flask, request, abort, render_template_string

import logging
import sys

app = Flask(__name__)

# --- logging to stdout (so journalctl shows app.logger.info) ---
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    force=True,
)
app.logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

if not any(isinstance(h, logging.StreamHandler) for h in app.logger.handlers):
    app.logger.addHandler(handler)

app.logger.propagate = False

DB_PATH = Path(__file__).with_name("market.db")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "bumala-admin-2025")

# =========================
# PILOT: Main categories
# =========================
PILOT_CATEGORIES: List[Tuple[str, str]] = [
    ("1", "Shops & Daily Needs"),
    ("2", "Food & Drinks"),
    ("3", "Transport"),
    ("4", "Services (Fundis)"),
    ("5", "Farming & Inputs"),
    ("6", "Health & Care"),
    ("7", "Education & Community"),
]

# Transport subcategories (submenu)
TRANSPORT_SUBCATS: List[Tuple[str, str]] = [
    ("1", "Riders"),
    ("2", "Pickups"),
    ("3", "Lorries"),
]

# PILOT villages (fixed for now)
PILOT_VILLAGES: List[Tuple[str, str]] = [
    ("1", "Sega"),
    ("2", "Bumala"),
    ("3", "Murende"),
]

# =========================
# In-memory session state
# (fine for pilot; resets on restart)
# =========================
SESSIONS: Dict[str, Dict[str, Any]] = {}
RECENT_LIMIT = 5

# =========================
# Database
# =========================
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            phone TEXT NOT NULL,
            village TEXT NOT NULL DEFAULT 'Bumala',
            created_at TEXT NOT NULL
        );
        """
    )

    # Ensure village column exists (older DB safety)
    cur.execute("PRAGMA table_info(businesses);")
    cols = [r[1] for r in cur.fetchall()]
    if "village" not in cols:
        cur.execute(
            "ALTER TABLE businesses ADD COLUMN village TEXT NOT NULL DEFAULT 'Bumala';"
        )
    conn.commit()
    conn.close()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {"recent": [], "add": {}}
    return SESSIONS[session_id]


def add_recent(session: Dict[str, Any], phone: str) -> None:
    if not phone:
        return
    recent = session.get("recent", [])
    if phone in recent:
        recent.remove(phone)
    recent.insert(0, phone)
    session["recent"] = recent[:RECENT_LIMIT]


def category_label(choice: str) -> Optional[str]:
    for k, v in PILOT_CATEGORIES:
        if k == choice:
            return v
    return None


def transport_subcat_label(choice: str) -> Optional[str]:
    for k, v in TRANSPORT_SUBCATS:
        if k == choice:
            return v
    return None


def village_label(choice: str) -> Optional[str]:
    for k, v in PILOT_VILLAGES:
        if k == choice:
            return v
    return None


def normalize_phone(p: str) -> str:
    return p.replace("+", "").strip()


def normalize_category_for_storage(
    main_cat: str, transport_subcat: Optional[str] = None
) -> str:
    """
    Stores transport as "Transport - Riders/Pickups/Lorries".
    Non-transport stored as normal category label.
    """
    if main_cat != "Transport":
        return main_cat
    if transport_subcat:
        return f"Transport - {transport_subcat}"
    return "Transport"  # fallback / legacy


def transport_query_categories(subcat: str) -> List[str]:
    """
    Backwards compatible:
    - Old data stored as "Transport" will show under Pickups.
    """
    if subcat == "Riders":
        return ["Transport - Riders"]
    if subcat == "Pickups":
        return ["Transport - Pickups", "Transport"]  # include legacy
    if subcat == "Lorries":
        return ["Transport - Lorries"]
    return ["Transport"]


def list_latest_by_category(category: str, limit: int = 20) -> List[sqlite3.Row]:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, category, phone, village, created_at
        FROM businesses
        WHERE category = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (category, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def list_latest_by_categories(categories: List[str], limit: int = 20) -> List[sqlite3.Row]:
    conn = db()
    cur = conn.cursor()
    placeholders = ",".join(["?"] * len(categories))
    cur.execute(
        f"""
        SELECT id, name, category, phone, village, created_at
        FROM businesses
        WHERE category IN ({placeholders})
        ORDER BY id DESC
        LIMIT ?
        """,
        (*categories, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_business(name: str, category: str, phone: str, village: str) -> None:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO businesses (name, category, phone, village, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name.strip(), category.strip(), phone.strip(), village.strip(), utc_now_iso()),
    )
    conn.commit()
    conn.close()


# =========================
# USSD helpers
# =========================
def ussd_response(text: str) -> str:
    return text


def main_menu() -> str:
    return "\n".join(
        [
            "CON Village Marketplace (PILOT)",
            "1. Shops & Daily Needs",
            "2. Food & Drinks",
            "3. Transport",
            "4. Services (Fundis)",
            "5. Farming & Inputs",
            "6. Health & Care",
            "7. Education & Community",
            "8. Add / Update Business",
            "9. Recent numbers",
            "0. Help",
        ]
    )


def help_menu() -> str:
    return "\n".join(
        [
            "CON Help",
            "Use 1-7 to browse categories.",
            "Transport has sub-menu: Riders / Pickups / Lorries.",
            "Use 8 to add your business (choose village first).",
            "Use 9 to see numbers you viewed in this session.",
            "0. Back",
        ]
    )


def format_list(title: str, rows: List[sqlite3.Row], show_recent: bool = True) -> str:
    header = f"CON {title}"
    if not rows:
        lines = [header, "No listings yet.", "0. Back"]
        if show_recent:
            lines.append("9. Recent numbers")
        return "\n".join(lines)

    lines = [header]
    i = 1
    for r in rows:
        name = r["name"]
        phone = r["phone"]
        village = r["village"]
        lines.append(f"{i}. {name} ({village})")
        lines.append(f"   Call: {phone}")
        i += 1
        if i > 9:
            break
    lines.append("0. Back")
    if show_recent:
        lines.append("9. Recent numbers")
    return "\n".join(lines)


def transport_menu() -> str:
    lines = ["CON Transport"]
    for k, v in TRANSPORT_SUBCATS:
        lines.append(f"{k}. {v}")
    lines.append("0. Back")
    return "\n".join(lines)


# =========================
# USSD endpoint
# =========================
@app.route("/", methods=["POST"])
def ussd_root_alias():
    return ussd()


@app.route("/ussd", methods=["POST"])
def ussd():
    session_id = request.form.get("sessionId", "").strip()
    phone_number = request.form.get("phoneNumber", "").strip()
    text = request.form.get("text", "").strip()

    app.logger.info("AT USSD: sessionId=%s phone=%s text=%s", session_id, phone_number, text)

    if not session_id:
        abort(400, "Missing sessionId")

    session = get_session(session_id)
    parts = text.split("*") if text else []
    # Africa's Talking pagination: they inject 98 as "MORE".
    # Remove ALL "98" tokens so flows like 98*8*98*8 don't break the menu state.
    # (Safe for our pilot: users never type 98 as real input)
    parts = [p for p in parts if p.strip() != "98"]





    # MAIN MENU
    if len(parts) == 0 or parts == [""]:
        return ussd_response(main_menu()), 200

    choice = parts[0].strip()

    # HELP / BACK
    if choice == "0":
        if len(parts) == 1:
            return ussd_response(help_menu()), 200
        return ussd_response(main_menu()), 200

    # RECENT
    if choice == "9":
        recent = session.get("recent", [])
        lines = ["CON Recent numbers (this session):"]
        if not recent:
            lines += ["None yet.", "0. Back"]
        else:
            for i, num in enumerate(recent[:RECENT_LIMIT], start=1):
                lines.append(f"{i}. {num}")
            lines.append("0. Back")
        return ussd_response("\n".join(lines)), 200

    # CATEGORY BROWSE
    cat = category_label(choice)

    # =========================
    # Transport submenu (WITH BACK SUPPORT)
    # =========================
    if cat == "Transport":
        # 3 -> show submenu
        if len(parts) == 1:
            return ussd_response(transport_menu()), 200
        # 3*0 -> back to MAIN menu (user pressed 0 while in Transport menu)
        if len(parts) == 2 and parts[1].strip() == "0":
            return ussd_response(main_menu()), 200

        # 3*1*0 / 3*2*0 / 3*3*0 -> back to Transport menu
        if len(parts) >= 3 and parts[-1].strip() == "0":
            return ussd_response(transport_menu()), 200

        sub_choice = parts[1].strip()
        sub_label = transport_subcat_label(sub_choice)
        if not sub_label:
            return ussd_response(
                "CON Invalid option.\n1. Riders\n2. Pickups\n3. Lorries\n0. Back"
            ), 200

        rows = list_latest_by_categories(transport_query_categories(sub_label), limit=20)
        for r in rows[:RECENT_LIMIT]:
            add_recent(session, r["phone"])
        return ussd_response(format_list(f"Transport - {sub_label} (latest):", rows)), 200

    # Other categories 1-7
    if cat and choice in {c[0] for c in PILOT_CATEGORIES}:
        rows = list_latest_by_category(cat, limit=20)
        for r in rows[:RECENT_LIMIT]:
            add_recent(session, r["phone"])
        return ussd_response(format_list(f"{cat} (latest):", rows)), 200

    # =========================
    # ADD / UPDATE (Village-first)
    # =========================
    if choice == "8":
        add_state = session.get("add", {})

        # Step A: choose village
        if len(parts) == 1:
            lines = ["CON Choose your village:"]
            for k, v in PILOT_VILLAGES:
                lines.append(f"{k}. {v}")
            lines.append("0. Back")
            session["add"] = {}
            return ussd_response("\n".join(lines)), 200

        # Step A2: store village
        if len(parts) == 2:
            v_choice = parts[1].strip()
            v_label = village_label(v_choice)
            if not v_label:
                return ussd_response("CON Invalid village. Choose 1-3.\n0. Back"), 200
            add_state["village"] = v_label
            session["add"] = add_state
            return ussd_response("CON Enter business name:\n0. Back"), 200

        # Step B: store name, show categories
        if len(parts) == 3:
            name = parts[2].strip()
            if not name:
                return ussd_response("CON Please enter a business name:\n0. Back"), 200
            add_state["name"] = name
            session["add"] = add_state
            lines = ["CON Choose category:"]
            for k, v in PILOT_CATEGORIES:
                lines.append(f"{k}. {v}")
            lines.append("0. Back")
            return ussd_response("\n".join(lines)), 200

        # Step C: store category, if Transport ask subcat, else confirm
        if len(parts) == 4:
            cat_choice = parts[3].strip()
            cat_label = category_label(cat_choice)
            if not cat_label:
                return ussd_response("CON Invalid category. Choose 1-7.\n0. Back"), 200

            add_state["category_main"] = cat_label
            session["add"] = add_state

            # If Transport -> ask subcat
            if cat_label == "Transport":
                lines = ["CON Transport type:"]
                for k, v in TRANSPORT_SUBCATS:
                    lines.append(f"{k}. {v}")
                lines.append("0. Back")
                return ussd_response("\n".join(lines)), 200

            # Non-transport -> confirm
            v = add_state.get("village", "Bumala")
            n = add_state.get("name", "")
            c = cat_label
            p = normalize_phone(phone_number)

            return ussd_response(
                "\n".join(
                    [
                        "CON Confirm:",
                        f"Village: {v}",
                        f"Name: {n}",
                        f"Category: {c}",
                        f"Phone:  {p}",
                        "1. Confirm",
                        "2. Cancel",
                        "0. Back",
                    ]
                )
            ), 200

        # Step C2: transport subcat chosen, then confirm
        if len(parts) == 5 and add_state.get("category_main") == "Transport":
            sub_choice = parts[4].strip()
            sub_label = transport_subcat_label(sub_choice)
            if not sub_label:
                return ussd_response(
                    "CON Invalid option.\n1. Riders\n2. Pickups\n3. Lorries\n0. Back"
                ), 200

            add_state["category_sub"] = sub_label
            session["add"] = add_state

            v = add_state.get("village", "Bumala")
            n = add_state.get("name", "")
            c = normalize_category_for_storage("Transport", sub_label)
            p = normalize_phone(phone_number)

            return ussd_response(
                "\n".join(
                    [
                        "CON Confirm:",
                        f"Village: {v}",
                        f"Name: {n}",
                        f"Category: {c}",
                        f"Phone:  {p}",
                        "1. Confirm",
                        "2. Cancel",
                        "0. Back",
                    ]
                )
            ), 200

        # Confirm / Cancel
        if len(parts) >= 5:
            # non-transport: action is parts[4]
            # transport: action is parts[5] (because parts[4]=subcat)
            if add_state.get("category_main") == "Transport":
                if len(parts) < 6:
                    return ussd_response("CON Choose 1 to confirm or 2 to cancel.\n0. Back"), 200
                action = parts[5].strip()
            else:
                action = parts[4].strip()

            if action == "2":
                session["add"] = {}
                return ussd_response("END Cancelled."), 200

            if action == "1":
                v = add_state.get("village", "Bumala")
                n = (add_state.get("name") or "").strip()
                main = (add_state.get("category_main") or "").strip()
                sub = (add_state.get("category_sub") or "").strip() if main == "Transport" else None
                p = normalize_phone(phone_number)

                if not (v and n and main and p):
                    session["add"] = {}
                    return ussd_response("END Missing data. Please try again."), 200

                final_cat = normalize_category_for_storage(main, sub if main == "Transport" else None)
                insert_business(n, final_cat, p, v)
                session["add"] = {}
                return ussd_response("END Saved! You are now listed. Thank you."), 200

            return ussd_response("CON Invalid option.\n1. Confirm\n2. Cancel\n0. Back"), 200

    # Unknown input -> main menu
    return ussd_response(main_menu()), 200


# =========================
# Menu page (browser view)
# =========================
@app.route("/menu", methods=["GET"])
def menu_page():
    html = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>USSD Menu - Village Marketplace (PILOT)</title>
      <style>
        body { font-family: system-ui, -apple-system, Arial; margin: 24px; line-height: 1.5; background:#f6f7f8; }
        .card { max-width: 980px; margin: 0 auto; background:white; border-radius: 12px; padding: 24px; box-shadow: 0 4px 14px rgba(0,0,0,.08); }
        h1 { margin-top: 0; }
        pre { background: #f2f2f2; padding: 16px; border-radius: 8px; overflow:auto; }
        .small { color:#666; font-size: 13px; }
        .row { display:flex; gap:16px; flex-wrap:wrap; }
        .col { flex: 1 1 420px; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Village Marketplace (PILOT)</h1>
        <p class="small">Visual representation of the live USSD menu (for browsers, NGOs, and demos).</p>

        <div class="row">
          <div class="col">
            <h3>Main USSD Menu</h3>
            <pre>
CON Village Marketplace (PILOT)
1. Shops & Daily Needs
2. Food & Drinks
3. Transport
4. Services (Fundis)
5. Farming & Inputs
6. Health & Care
7. Education & Community
8. Add / Update Business
9. Recent numbers
0. Help
            </pre>
          </div>

          <div class="col">
            <h3>Transport sub-menu</h3>
            <pre>
CON Transport
1. Riders
2. Pickups
3. Lorries
0. Back
            </pre>
          </div>
        </div>

        <h3>Add / Update flow (Village-first)</h3>
        <pre>
8. Add / Update Business
→ Choose your village: Sega / Bumala / Murende
→ Enter business name
→ Choose category
→ If category = Transport → choose Riders / Pickups / Lorries
→ Confirm
        </pre>

        <p class="small">
          Kenya dial (example): <b>*789*565656#</b> • Web: <b>https://api.murende.org/menu</b>
        </p>
      </div>
    </body>
    </html>
    """
    return html, 200


# =========================
# Monitoring dashboard (token-protected, read-only)
# =========================
DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Village Marketplace - Dashboard</title>
  <style>
    body { font-family: system-ui, -apple-system, Arial; margin: 24px; background:#f6f7f8; }
    .card { max-width: 1100px; margin: 0 auto 16px; background:white; border-radius: 12px; padding: 18px 20px; box-shadow: 0 4px 14px rgba(0,0,0,.08); }
    h1 { margin: 0 0 6px; }
    .small { color:#666; font-size: 12px; }
    table { border-collapse: collapse; width: 100%; font-size: 14px; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background: #f3f3f3; text-align: left; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 900px){ .grid { grid-template-columns: 1fr; } }
    .pill { display:inline-block; padding:2px 8px; border-radius:999px; background:#eef2ff; font-size:12px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Village Marketplace - Dashboard</h1>
    <div class="small">
      Read-only monitoring • Keep this link private (token-protected).<br>
      Updated: <b>{{ now }}</b>
    </div>
  </div>

  <div class="card">
    <div class="grid">
      <div>
        <h3>Totals</h3>
        <table>
          <tr><th>Total listings</th><td>{{ totals.total }}</td></tr>
          <tr><th>Total villages</th><td>{{ totals.villages }}</td></tr>
          <tr><th>Total categories</th><td>{{ totals.categories }}</td></tr>
        </table>
      </div>
      <div>
        <h3>Transport breakdown</h3>
        <table>
          <tr><th>Riders</th><td>{{ transport.riders }}</td></tr>
          <tr><th>Pickups</th><td>{{ transport.pickups }}</td></tr>
          <tr><th>Lorries</th><td>{{ transport.lorries }}</td></tr>
          <tr><th>Legacy “Transport”</th><td>{{ transport.legacy }}</td></tr>
        </table>
        <div class="small">Legacy “Transport” is shown under <span class="pill">Pickups</span> in USSD for backward compatibility.</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h3>Counts by village</h3>
    <table>
      <thead><tr><th>Village</th><th>Count</th></tr></thead>
      <tbody>
      {% for row in by_village %}
        <tr><td>{{ row["village"] }}</td><td>{{ row["cnt"] }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h3>Counts by category</h3>
    <table>
      <thead><tr><th>Category</th><th>Count</th></tr></thead>
      <tbody>
      {% for row in by_category %}
        <tr><td>{{ row["category"] }}</td><td>{{ row["cnt"] }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h3>Latest records</h3>
    <table>
      <thead>
        <tr><th>ID</th><th>Name</th><th>Category</th><th>Village</th><th>Phone</th><th>Created</th></tr>
      </thead>
      <tbody>
      {% for r in latest %}
        <tr>
          <td>{{ r["id"] }}</td>
          <td>{{ r["name"] }}</td>
          <td>{{ r["category"] }}</td>
          <td>{{ r["village"] }}</td>
          <td>{{ r["phone"] }}</td>
          <td>{{ r["created_at"] }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="card small">
    URLs:
    <ul>
      <li>/menu (public): <b>https://api.murende.org/menu</b></li>
      <li>/dashboard (private): <b>https://api.murende.org/dashboard?token=YOUR_TOKEN</b></li>
    </ul>
  </div>
</body>
</html>
"""


@app.route("/dashboard", methods=["GET"])
def dashboard():
    token = request.args.get("token", "")
    if token != ADMIN_TOKEN:
        abort(403)

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS cnt FROM businesses;")
    total = int(cur.fetchone()["cnt"])

    cur.execute("SELECT COUNT(DISTINCT village) AS cnt FROM businesses;")
    villages = int(cur.fetchone()["cnt"])

    cur.execute("SELECT COUNT(DISTINCT category) AS cnt FROM businesses;")
    categories = int(cur.fetchone()["cnt"])

    cur.execute(
        "SELECT village, COUNT(*) AS cnt FROM businesses GROUP BY village ORDER BY cnt DESC, village ASC;"
    )
    by_village = cur.fetchall()

    cur.execute(
        "SELECT category, COUNT(*) AS cnt FROM businesses GROUP BY category ORDER BY cnt DESC, category ASC;"
    )
    by_category = cur.fetchall()

    cur.execute(
        "SELECT id,name,category,village,phone,created_at FROM businesses ORDER BY id DESC LIMIT 50;"
    )
    latest = cur.fetchall()

    def count_cat(cat: str) -> int:
        cur.execute("SELECT COUNT(*) AS cnt FROM businesses WHERE category = ?;", (cat,))
        return int(cur.fetchone()["cnt"])

    riders = count_cat("Transport - Riders")
    pickups = count_cat("Transport - Pickups")
    lorries = count_cat("Transport - Lorries")
    legacy = count_cat("Transport")

    conn.close()

    now = utc_now_iso()
    return render_template_string(
        DASHBOARD_HTML,
        now=now,
        totals={"total": total, "villages": villages, "categories": categories},
        transport={"riders": riders, "pickups": pickups, "lorries": lorries, "legacy": legacy},
        by_village=by_village,
        by_category=by_category,
        latest=latest,
    ), 200


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000)
