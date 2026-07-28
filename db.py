#!/usr/bin/env python3
"""
VØRTΞX System Bot — PostgreSQL Database Module
All-in-one database handler for all 10 cogs.
Uses pg8000 (pure Python, no compilation needed).
"""
from pg8000.native import Connection, literal
from typing import Optional, Any
import json, time
from pathlib import Path

# ── Connection ────────────────────────────────────────────────────────
DB_CONFIG = {
    "user": "postgres",
    "password": "61174271082a",
    "host": "db.fxyfsoomgltikdmxaouu.supabase.co",
    "port": 5432,
    "database": "postgres",
}

_conn: Optional[Connection] = None

def get_db() -> Connection:
    global _conn
    if _conn is None:
        _conn = Connection(**DB_CONFIG)
        _conn.run("SET statement_timeout = '30s'")
    # Ping check
    try:
        _conn.run("SELECT 1")
    except Exception:
        _conn = Connection(**DB_CONFIG)
    return _conn

def close():
    global _conn
    if _conn:
        try:
            _conn.close()
        except:
            pass
        _conn = None

# ── Guild Config ─────────────────────────────────────────────────────
def get_guild_config(guild_id: int) -> dict:
    db = get_db()
    row = db.run("SELECT * FROM guild_config WHERE guild_id = :gid", gid=guild_id)
    if not row:
        return {}
    cols = [c["name"] for c in db.columns]
    return dict(zip(cols, row[0]))

def set_guild_config(guild_id: int, **kwargs):
    db = get_db()
    # Upsert
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    cols = ", ".join(kwargs.keys())
    vals = ", ".join(f":{k}" for k in kwargs)
    kwargs["gid"] = guild_id
    db.run(f"""
        INSERT INTO guild_config (guild_id, {cols})
        VALUES (:gid, {vals})
        ON CONFLICT (guild_id) DO UPDATE SET {sets}, updated_at = NOW()
    """, **kwargs)

# ── Levels ────────────────────────────────────────────────────────────
def get_user_level(guild_id: int, user_id: int) -> dict:
    db = get_db()
    row = db.run("SELECT * FROM user_levels WHERE guild_id = :gid AND user_id = :uid",
                  gid=guild_id, uid=user_id)
    if not row:
        return {"xp": 0, "level": 0, "total_xp": 0}
    cols = [c["name"] for c in db.columns]
    return dict(zip(cols, row[0]))

def set_user_level(guild_id: int, user_id: int, **kwargs):
    db = get_db()
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    kwargs["gid"] = guild_id
    kwargs["uid"] = user_id
    db.run(f"""
        INSERT INTO user_levels (guild_id, user_id, {', '.join(kwargs.keys() - {'gid', 'uid'})})
        VALUES (:gid, :uid, {', '.join(f':{k}' for k in kwargs if k not in ('gid','uid'))})
        ON CONFLICT (guild_id, user_id) DO UPDATE SET {sets}
    """, **kwargs)

def get_leaderboard(guild_id: int, limit: int = 10) -> list:
    db = get_db()
    rows = db.run("""
        SELECT user_id, xp, level, total_xp
        FROM user_levels WHERE guild_id = :gid
        ORDER BY total_xp DESC LIMIT :lim
    """, gid=guild_id, lim=limit)
    cols = ["user_id", "xp", "level", "total_xp"]
    return [dict(zip(cols, r)) for r in rows]

def get_rank(guild_id: int, user_id: int) -> int:
    db = get_db()
    row = db.run("""
        SELECT COUNT(*) + 1 FROM user_levels
        WHERE guild_id = :gid AND total_xp > (
            SELECT COALESCE(total_xp, 0) FROM user_levels
            WHERE guild_id = :gid AND user_id = :uid
        )
    """, gid=guild_id, uid=user_id)
    return row[0][0] if row else 0

# ── Stats ─────────────────────────────────────────────────────────────
def incr_stat(key: str, amount: int = 1):
    db = get_db()
    db.run("""
        INSERT INTO stats (key, value) VALUES (:k, :a)
        ON CONFLICT (key) DO UPDATE SET value = stats.value + :a, updated_at = NOW()
    """, k=key, a=amount)

def get_stat(key: str) -> int:
    db = get_db()
    row = db.run("SELECT value FROM stats WHERE key = :k", k=key)
    return row[0][0] if row else 0

def get_all_stats() -> dict:
    db = get_db()
    rows = db.run("SELECT key, value FROM stats")
    return {r[0]: r[1] for r in rows}

# ── Audit Log ─────────────────────────────────────────────────────────
def add_audit(action: str, detail: str = "", guild_id: int = 0, user_id: int = 0):
    db = get_db()
    db.run("""
        INSERT INTO audit_log (action, detail, guild_id, user_id)
        VALUES (:a, :d, :gid, :uid)
    """, a=action, d=detail, gid=guild_id, uid=user_id)

def get_audit_log(guild_id: int = 0, limit: int = 20) -> list:
    db = get_db()
    if guild_id:
        rows = db.run("""
            SELECT action, detail, created_at FROM audit_log
            WHERE guild_id = :gid ORDER BY created_at DESC LIMIT :lim
        """, gid=guild_id, lim=limit)
    else:
        rows = db.run("""
            SELECT action, detail, created_at FROM audit_log
            ORDER BY created_at DESC LIMIT :lim
        """, lim=limit)
    cols = ["action", "detail", "time"]
    return [dict(zip(cols, r)) for r in rows]

# ── Custom Commands ───────────────────────────────────────────────────
def set_custom_command(guild_id: int, name: str, response: str, created_by: int = 0):
    db = get_db()
    db.run("""
        INSERT INTO custom_commands (guild_id, name, response, created_by)
        VALUES (:gid, :n, :r, :cb)
        ON CONFLICT (guild_id, name) DO UPDATE SET response = :r, created_by = :cb
    """, gid=guild_id, n=name.lower(), r=response, cb=created_by)

def del_custom_command(guild_id: int, name: str) -> bool:
    db = get_db()
    r = db.run("DELETE FROM custom_commands WHERE guild_id = :gid AND name = :n",
                gid=guild_id, n=name.lower())
    return r.row_count > 0

def get_custom_command(guild_id: int, name: str) -> Optional[str]:
    db = get_db()
    row = db.run("SELECT response FROM custom_commands WHERE guild_id = :gid AND name = :n",
                  gid=guild_id, n=name.lower())
    return row[0][0] if row else None

def list_custom_commands(guild_id: int) -> list:
    db = get_db()
    rows = db.run("SELECT name, response FROM custom_commands WHERE guild_id = :gid ORDER BY name",
                  gid=guild_id)
    return [{"name": r[0], "response": r[1]} for r in rows]

# ── Reaction Roles ────────────────────────────────────────────────────
def add_reaction_role(guild_id: int, panel_id: str, channel_id: int,
                       message_id: int, title: str, role_id: int, label: str, emoji: str):
    db = get_db()
    db.run("""
        INSERT INTO reaction_roles (guild_id, panel_id, channel_id, message_id, title, role_id, label, emoji)
        VALUES (:gid, :pid, :cid, :mid, :t, :rid, :l, :e)
        ON CONFLICT (guild_id, panel_id, role_id) DO UPDATE SET label = :l, emoji = :e
    """, gid=guild_id, pid=panel_id, cid=channel_id, mid=message_id, t=title,
         rid=role_id, l=label, e=emoji)

def remove_reaction_role(guild_id: int, panel_id: str, role_id: int):
    db = get_db()
    db.run("DELETE FROM reaction_roles WHERE guild_id = :gid AND panel_id = :pid AND role_id = :rid",
            gid=guild_id, pid=panel_id, rid=role_id)

def get_reaction_panels(guild_id: int) -> list:
    db = get_db()
    rows = db.run("""
        SELECT DISTINCT panel_id, channel_id, message_id, title
        FROM reaction_roles WHERE guild_id = :gid ORDER BY panel_id
    """, gid=guild_id)
    panels = []
    for r in rows:
        pid, cid, mid, title = r
        roles = db.run("""
            SELECT role_id, label, emoji FROM reaction_roles
            WHERE guild_id = :gid AND panel_id = :pid
        """, gid=guild_id, pid=pid)
        panels.append({
            "id": pid, "channel_id": cid, "message_id": mid, "title": title,
            "roles": [{"role_id": r[0], "label": r[1], "emoji": r[2]} for r in roles]
        })
    return panels

def get_reaction_panel_by_message(message_id: int) -> Optional[dict]:
    db = get_db()
    rows = db.run("""
        SELECT DISTINCT guild_id, panel_id, channel_id, message_id, title
        FROM reaction_roles WHERE message_id = :mid
    """, mid=message_id)
    if not rows:
        return None
    r = rows[0]
    pid = r[1]
    roles = db.run("""
        SELECT role_id, label, emoji FROM reaction_roles
        WHERE guild_id = :gid AND panel_id = :pid
    """, gid=r[0], pid=pid)
    return {
        "guild_id": r[0], "id": pid, "channel_id": r[2],
        "message_id": r[3], "title": r[4],
        "roles": [{"role_id": r[0], "label": r[1], "emoji": r[2]} for r in roles]
    }

# ── Anti-Raid ─────────────────────────────────────────────────────────
def get_antiraid_config(guild_id: int) -> dict:
    db = get_db()
    row = db.run("SELECT * FROM antiraid_config WHERE guild_id = :gid", gid=guild_id)
    if not row:
        return {}
    cols = [c["name"] for c in db.columns]
    d = dict(zip(cols, row[0]))
    # Convert arrays
    for k in ("whitelist_roles", "bad_words"):
        if k in d and isinstance(d[k], str):
            d[k] = json.loads(d[k]) if d[k].startswith("[") else (d[k][1:-1].split(",") if d[k] != "{}" else [])
    return d

def set_antiraid_config(guild_id: int, **kwargs):
    db = get_db()
    # Convert arrays to postgres format
    for k in ("whitelist_roles", "bad_words"):
        if k in kwargs and isinstance(kwargs[k], (list, tuple)):
            kwargs[k] = "{" + ",".join(str(x) for x in kwargs[k]) + "}"
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    cols = ", ".join(kwargs.keys())
    vals = ", ".join(f":{k}" for k in kwargs)
    kwargs["gid"] = guild_id
    db.run(f"""
        INSERT INTO antiraid_config (guild_id, {cols})
        VALUES (:gid, {vals})
        ON CONFLICT (guild_id) DO UPDATE SET {sets}
    """, **kwargs)

# ── Broadcast ─────────────────────────────────────────────────────────
def add_broadcast(guild_id: int, channel_ids: list, title: str, 
                   message: str, sent_by: int = 0, sent_to: int = 0):
    db = get_db()
    db.run("""
        INSERT INTO broadcast_history (guild_id, channel_ids, title, message, sent_by, sent_to)
        VALUES (:gid, :cids, :t, :m, :sb, :st)
    """, gid=guild_id, 
         cids="{" + ",".join(str(c) for c in channel_ids) + "}",
         t=title, m=message, sb=sent_by, st=sent_to)

def get_broadcast_history(guild_id: int, limit: int = 10) -> list:
    db = get_db()
    rows = db.run("""
        SELECT id, channel_ids, title, message, sent_to, created_at
        FROM broadcast_history WHERE guild_id = :gid
        ORDER BY created_at DESC LIMIT :lim
    """, gid=guild_id, lim=limit)
    cols = ["id", "channel_ids", "title", "message", "sent_to", "time"]
    return [dict(zip(cols, r)) for r in rows]

# ── Tickets ───────────────────────────────────────────────────────────
def create_ticket(guild_id: int, user_id: int, category: str = "general") -> dict:
    db = get_db()
    db.run("""
        INSERT INTO tickets (guild_id, user_id, category)
        VALUES (:gid, :uid, :cat)
    """, gid=guild_id, uid=user_id, cat=category)
    # Get the inserted row
    row = db.run("SELECT * FROM tickets WHERE id = LASTVAL()")
    cols = [c["name"] for c in db.columns]
    return dict(zip(cols, row[0]))

def close_ticket(ticket_id: int, closed_by: int = 0):
    db = get_db()
    db.run("""
        UPDATE tickets SET status = 'closed', closed_at = NOW(), closed_by = :cb
        WHERE id = :tid
    """, tid=ticket_id, cb=closed_by)

def get_user_ticket(guild_id: int, user_id: int) -> Optional[dict]:
    db = get_db()
    row = db.run("""
        SELECT * FROM tickets WHERE guild_id = :gid AND user_id = :uid AND status = 'open'
        LIMIT 1
    """, gid=guild_id, uid=user_id)
    if not row:
        return None
    cols = [c["name"] for c in db.columns]
    return dict(zip(cols, row[0]))

def get_all_tickets(guild_id: int, status: str = None) -> list:
    db = get_db()
    if status:
        rows = db.run("""
            SELECT * FROM tickets WHERE guild_id = :gid AND status = :s
            ORDER BY created_at DESC
        """, gid=guild_id, s=status)
    else:
        rows = db.run("""
            SELECT * FROM tickets WHERE guild_id = :gid
            ORDER BY created_at DESC
        """, gid=guild_id)
    if not rows:
        return []
    cols = [c["name"] for c in db.columns]
    return [dict(zip(cols, r)) for r in rows]

# ── Warns ─────────────────────────────────────────────────────────────
def add_warn(guild_id: int, user_id: int, moderator_id: int = 0, reason: str = ""):
    db = get_db()
    db.run("""
        INSERT INTO warns (guild_id, user_id, moderator_id, reason)
        VALUES (:gid, :uid, :mid, :r)
    """, gid=guild_id, uid=user_id, mid=moderator_id, r=reason)

def get_warns(guild_id: int, user_id: int) -> list:
    db = get_db()
    rows = db.run("""
        SELECT id, reason, moderator_id, created_at FROM warns
        WHERE guild_id = :gid AND user_id = :uid
        ORDER BY created_at DESC
    """, gid=guild_id, uid=user_id)
    cols = ["id", "reason", "moderator_id", "time"]
    return [dict(zip(cols, r)) for r in rows]

def clear_warns(guild_id: int, user_id: int):
    db = get_db()
    db.run("DELETE FROM warns WHERE guild_id = :gid AND user_id = :uid",
            gid=guild_id, uid=user_id)

# ── Welcome History ───────────────────────────────────────────────────
def add_welcome(guild_id: int, user_id: int):
    db = get_db()
    db.run("INSERT INTO welcome_history (guild_id, user_id) VALUES (:gid, :uid)",
            gid=guild_id, uid=user_id)

def get_welcome_count(guild_id: int) -> int:
    db = get_db()
    row = db.run("SELECT COUNT(*) FROM welcome_history WHERE guild_id = :gid",
                  gid=guild_id)
    return row[0][0] if row else 0

# ── Init first-time data ──────────────────────────────────────────────
def init_defaults():
    """Set default stats if they don't exist"""
    db = get_db()
    defaults = [
        ("total_commands", 0),
        ("total_guilds", 0),
        ("total_users", 0),
        ("bot_started", int(time.time())),
    ]
    for k, v in defaults:
        db.run("""
            INSERT INTO stats (key, value) VALUES (:k, :v)
            ON CONFLICT (key) DO NOTHING
        """, k=k, v=v)
