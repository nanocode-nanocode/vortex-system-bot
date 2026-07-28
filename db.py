#!/usr/bin/env python3
"""
VØRTΞX System Bot — PostgreSQL Database Module (Resilient)
All-in-one database handler for all 10 cogs.
Uses pg8000 (pure Python, no compilation needed).
Falls back to JSON when PostgreSQL is unavailable.
"""
from pg8000.native import Connection
from typing import Optional
import json, time
from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Connection ────────────────────────────────────────────────────────
DB_CONFIG = {
    "user": "postgres",
    "password": "61174271082s",
    "host": "db.sifijctyygnqluuegzyu.supabase.co",
    "port": 5432,
    "database": "postgres",
}

_conn: Optional[Connection] = None
_DB_FAILED = False

def get_db() -> Optional[Connection]:
    """Get database connection with retry. Returns None if unavailable."""
    global _conn, _DB_FAILED
    if _DB_FAILED:
        return None
    try:
        if _conn is None:
            _conn = Connection(**DB_CONFIG)
            _conn.run("SET statement_timeout = '30s'")
        # Ping
        _conn.run("SELECT 1")
        return _conn
    except Exception:
        try:
            _conn = Connection(**DB_CONFIG)
            _conn.run("SET statement_timeout = '30s'")
            _DB_FAILED = False
            return _conn
        except Exception:
            _conn = None
            _DB_FAILED = True
            return None

def close():
    global _conn
    if _conn:
        try: _conn.close()
        except: pass
        _conn = None

def is_connected() -> bool:
    return get_db() is not None

# ── JSON fallback helpers ─────────────────────────────────────────────
def _json_path(table: str) -> Path:
    return DATA_DIR / f"{table}.json"

def _json_read(table: str) -> dict:
    p = _json_path(table)
    return json.loads(p.read_text()) if p.exists() else {}

def _json_write(table: str, data: dict):
    _json_path(table).write_text(json.dumps(data, indent=2, default=str))

def _try_db(fn, fallback=None):
    """Run fn(db) if DB connected, else return fallback."""
    db = get_db()
    if db:
        try:
            return fn(db)
        except Exception:
            return fallback
    return fallback

# ── Guild Config ─────────────────────────────────────────────────────
def get_guild_config(guild_id: int) -> dict:
    db = get_db()
    if not db:
        return _json_read("guild_config").get(str(guild_id), {"language": "ar"})
    try:
        row = db.run("SELECT * FROM guild_config WHERE guild_id = :gid", gid=guild_id)
        if not row:
            return {"language": "ar"}
        cols = [c["name"] for c in db.columns]
        return dict(zip(cols, row[0]))
    except Exception:
        return _json_read("guild_config").get(str(guild_id), {"language": "ar"})

def set_guild_config(guild_id: int, **kwargs):
    db = get_db()
    if not db:
        data = _json_read("guild_config")
        data[str(guild_id)] = {**data.get(str(guild_id), {}), **kwargs}
        return _json_write("guild_config", data)
    try:
        kwargs.setdefault("language", "ar")
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        cols = ", ".join(kwargs.keys())
        vals = ", ".join(f":{k}" for k in kwargs)
        kwargs["gid"] = guild_id
        db.run(f"""
            INSERT INTO guild_config (guild_id, {cols})
            VALUES (:gid, {vals})
            ON CONFLICT (guild_id) DO UPDATE SET {sets}, updated_at = NOW()
        """, **kwargs)
    except Exception:
        data = _json_read("guild_config")
        data[str(guild_id)] = {**data.get(str(guild_id), {}), **kwargs}
        _json_write("guild_config", data)

# ── Levels ────────────────────────────────────────────────────────────
def get_user_level(guild_id: int, user_id: int) -> dict:
    db = get_db()
    if not db:
        data = _json_read("user_levels")
        return data.get(f"{guild_id}:{user_id}", {"xp": 0, "level": 0, "total_xp": 0})
    try:
        row = db.run("SELECT * FROM user_levels WHERE guild_id = :gid AND user_id = :uid",
                      gid=guild_id, uid=user_id)
        if not row:
            return {"xp": 0, "level": 0, "total_xp": 0}
        cols = [c["name"] for c in db.columns]
        return dict(zip(cols, row[0]))
    except Exception:
        data = _json_read("user_levels")
        return data.get(f"{guild_id}:{user_id}", {"xp": 0, "level": 0, "total_xp": 0})

def set_user_level(guild_id: int, user_id: int, **kwargs):
    db = get_db()
    if not db:
        data = _json_read("user_levels")
        key = f"{guild_id}:{user_id}"
        data[key] = {**data.get(key, {}), **kwargs}
        return _json_write("user_levels", data)
    try:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        kwargs["gid"] = guild_id
        kwargs["uid"] = user_id
        db.run(f"""
            INSERT INTO user_levels (guild_id, user_id, {', '.join(k for k in kwargs if k not in ('gid','uid'))})
            VALUES (:gid, :uid, {', '.join(f':{k}' for k in kwargs if k not in ('gid','uid'))})
            ON CONFLICT (guild_id, user_id) DO UPDATE SET {sets}
        """, **kwargs)
    except Exception:
        data = _json_read("user_levels")
        key = f"{guild_id}:{user_id}"
        data[key] = {**data.get(key, {}), **kwargs}
        _json_write("user_levels", data)

def get_leaderboard(guild_id: int, limit: int = 10) -> list:
    db = get_db()
    if not db:
        data = _json_read("user_levels")
        users = [(k.split(":")[1], v) for k, v in data.items() if k.startswith(f"{guild_id}:")]
        users.sort(key=lambda x: x[1].get("total_xp", 0), reverse=True)
        return [{"user_id": int(u[0]), **u[1]} for u in users[:limit]]
    try:
        rows = db.run("""
            SELECT user_id, xp, level, total_xp
            FROM user_levels WHERE guild_id = :gid
            ORDER BY total_xp DESC LIMIT :lim
        """, gid=guild_id, lim=limit)
        cols = ["user_id", "xp", "level", "total_xp"]
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []

def get_rank(guild_id: int, user_id: int) -> int:
    db = get_db()
    if not db:
        data = _json_read("user_levels")
        users = [(k, v.get("total_xp", 0)) for k, v in data.items() if k.startswith(f"{guild_id}:")]
        users.sort(key=lambda x: x[1], reverse=True)
        for i, (k, _) in enumerate(users):
            if k == f"{guild_id}:{user_id}":
                return i + 1
        return 0
    try:
        row = db.run("""
            SELECT COUNT(*) + 1 FROM user_levels
            WHERE guild_id = :gid AND total_xp > (
                SELECT COALESCE(total_xp, 0) FROM user_levels
                WHERE guild_id = :gid AND user_id = :uid
            )
        """, gid=guild_id, uid=user_id)
        return row[0][0] if row else 0
    except Exception:
        return 0

# ── Stats ─────────────────────────────────────────────────────────────
def set_stat(key: str, value: int):
    db = get_db()
    if not db:
        data = _json_read("stats")
        data[key] = {"value": value, "updated_at": time.time()}
        return _json_write("stats", data)
    try:
        db.run("""
            INSERT INTO stats (key, value) VALUES (:k, :v)
            ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = NOW()
        """, k=key, v=value)
    except Exception:
        data = _json_read("stats")
        data[key] = {"value": value, "updated_at": time.time()}
        _json_write("stats", data)

def incr_stat(key: str, amount: int = 1):
    db = get_db()
    if not db:
        data = _json_read("stats")
        old = data.get(key, {}).get("value", 0)
        data[key] = {"value": old + amount, "updated_at": time.time()}
        return _json_write("stats", data)
    try:
        db.run("""
            INSERT INTO stats (key, value) VALUES (:k, :a)
            ON CONFLICT (key) DO UPDATE SET value = stats.value + :a, updated_at = NOW()
        """, k=key, a=amount)
    except Exception:
        data = _json_read("stats")
        old = data.get(key, {}).get("value", 0)
        data[key] = {"value": old + amount, "updated_at": time.time()}
        _json_write("stats", data)

def get_stat(key: str) -> int:
    db = get_db()
    if not db:
        data = _json_read("stats")
        return data.get(key, {}).get("value", 0)
    try:
        row = db.run("SELECT value FROM stats WHERE key = :k", k=key)
        return row[0][0] if row else 0
    except Exception:
        data = _json_read("stats")
        return data.get(key, {}).get("value", 0)

def get_all_stats() -> dict:
    db = get_db()
    if not db:
        data = _json_read("stats")
        return {k: v.get("value", 0) for k, v in data.items()}
    try:
        rows = db.run("SELECT key, value FROM stats")
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}

# ── Audit Log ─────────────────────────────────────────────────────────
def add_audit(action: str, detail: str = "", guild_id: int = 0, user_id: int = 0):
    db = get_db()
    if not db:
        data = _json_read("audit_log")
        if not isinstance(data, list):
            data = []
        data.insert(0, {"action": action, "detail": detail, "guild_id": guild_id,
                         "user_id": user_id, "time": time.time()})
        return _json_write("audit_log", data)
    try:
        db.run("""
            INSERT INTO audit_log (action, detail, guild_id, user_id)
            VALUES (:a, :d, :gid, :uid)
        """, a=action, d=detail, gid=guild_id, uid=user_id)
    except Exception:
        data = _json_read("audit_log")
        if not isinstance(data, list):
            data = []
        data.insert(0, {"action": action, "detail": detail, "guild_id": guild_id,
                         "user_id": user_id, "time": time.time()})
        _json_write("audit_log", data)

def get_audit_log(guild_id: int = 0, limit: int = 20) -> list:
    db = get_db()
    if not db:
        data = _json_read("audit_log")
        if not isinstance(data, list):
            return []
        if guild_id:
            data = [d for d in data if d.get("guild_id") == guild_id]
        return data[:limit]
    try:
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
    except Exception:
        return []

# ── Custom Commands ───────────────────────────────────────────────────
def set_custom_command(guild_id: int, name: str, response: str, created_by: int = 0):
    db = get_db()
    if not db:
        data = _json_read("custom_commands")
        key = f"{guild_id}:{name.lower()}"
        data[key] = {"response": response, "created_by": created_by}
        return _json_write("custom_commands", data)
    try:
        db.run("""
            INSERT INTO custom_commands (guild_id, name, response, created_by)
            VALUES (:gid, :n, :r, :cb)
            ON CONFLICT (guild_id, name) DO UPDATE SET response = :r, created_by = :cb
        """, gid=guild_id, n=name.lower(), r=response, cb=created_by)
    except Exception:
        data = _json_read("custom_commands")
        key = f"{guild_id}:{name.lower()}"
        data[key] = {"response": response, "created_by": created_by}
        _json_write("custom_commands", data)

def del_custom_command(guild_id: int, name: str) -> bool:
    db = get_db()
    if not db:
        data = _json_read("custom_commands")
        key = f"{guild_id}:{name.lower()}"
        if key in data:
            del data[key]
            _json_write("custom_commands", data)
            return True
        return False
    try:
        r = db.run("DELETE FROM custom_commands WHERE guild_id = :gid AND name = :n",
                    gid=guild_id, n=name.lower())
        return r.row_count > 0
    except Exception:
        return False

def get_custom_command(guild_id: int, name: str) -> Optional[str]:
    db = get_db()
    if not db:
        data = _json_read("custom_commands")
        return data.get(f"{guild_id}:{name.lower()}", {}).get("response")
    try:
        row = db.run("SELECT response FROM custom_commands WHERE guild_id = :gid AND name = :n",
                      gid=guild_id, n=name.lower())
        return row[0][0] if row else None
    except Exception:
        return None

def list_custom_commands(guild_id: int) -> list:
    db = get_db()
    if not db:
        data = _json_read("custom_commands")
        return [{"name": k.split(":")[1], "response": v["response"]}
                for k, v in data.items() if k.startswith(f"{guild_id}:")]
    try:
        rows = db.run("SELECT name, response FROM custom_commands WHERE guild_id = :gid ORDER BY name",
                      gid=guild_id)
        return [{"name": r[0], "response": r[1]} for r in rows]
    except Exception:
        return []

# ── Reaction Roles ────────────────────────────────────────────────────
def add_reaction_role(guild_id: int, panel_id: str, channel_id: int,
                       message_id: int, title: str, role_id: int, label: str, emoji: str):
    db = get_db()
    if not db:
        data = _json_read("reaction_roles")
        key = f"{guild_id}:{panel_id}:{role_id}"
        data[key] = {"channel_id": channel_id, "message_id": message_id, "title": title,
                      "label": label, "emoji": emoji}
        return _json_write("reaction_roles", data)
    try:
        db.run("""
            INSERT INTO reaction_roles (guild_id, panel_id, channel_id, message_id, title, role_id, label, emoji)
            VALUES (:gid, :pid, :cid, :mid, :t, :rid, :l, :e)
            ON CONFLICT (guild_id, panel_id, role_id) DO UPDATE SET label = :l, emoji = :e
        """, gid=guild_id, pid=panel_id, cid=channel_id, mid=message_id, t=title,
             rid=role_id, l=label, e=emoji)
    except Exception:
        data = _json_read("reaction_roles")
        key = f"{guild_id}:{panel_id}:{role_id}"
        data[key] = {"channel_id": channel_id, "message_id": message_id, "title": title,
                      "label": label, "emoji": emoji}
        _json_write("reaction_roles", data)

def remove_reaction_role(guild_id: int, panel_id: str, role_id: int):
    db = get_db()
    if not db:
        data = _json_read("reaction_roles")
        key = f"{guild_id}:{panel_id}:{role_id}"
        data.pop(key, None)
        return _json_write("reaction_roles", data)
    try:
        db.run("DELETE FROM reaction_roles WHERE guild_id = :gid AND panel_id = :pid AND role_id = :rid",
                gid=guild_id, pid=panel_id, rid=role_id)
    except Exception:
        pass

def get_reaction_panels(guild_id: int) -> list:
    db = get_db()
    if not db:
        data = _json_read("reaction_roles")
        panels = {}
        for k, v in data.items():
            parts = k.split(":")
            if parts[0] == str(guild_id):
                pid = parts[1]
                if pid not in panels:
                    panels[pid] = {"id": pid, "channel_id": v["channel_id"],
                                    "message_id": v["message_id"], "title": v["title"], "roles": []}
                panels[pid]["roles"].append({"role_id": int(parts[2]), "label": v["label"], "emoji": v["emoji"]})
        return list(panels.values())
    try:
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
    except Exception:
        return []

def get_reaction_panel_by_message(message_id: int) -> Optional[dict]:
    db = get_db()
    if not db:
        return None
    try:
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
    except Exception:
        return None

# ── Anti-Raid ─────────────────────────────────────────────────────────
def get_antiraid_config(guild_id: int) -> dict:
    db = get_db()
    if not db:
        return _json_read("antiraid_config").get(str(guild_id), {})
    try:
        row = db.run("SELECT * FROM antiraid_config WHERE guild_id = :gid", gid=guild_id)
        if not row:
            return {}
        cols = [c["name"] for c in db.columns]
        d = dict(zip(cols, row[0]))
        for k in ("whitelist_roles", "bad_words"):
            if k in d and isinstance(d[k], str):
                d[k] = json.loads(d[k]) if d[k].startswith("[") else (d[k][1:-1].split(",") if d[k] != "{}" else [])
        return d
    except Exception:
        return _json_read("antiraid_config").get(str(guild_id), {})

def set_antiraid_config(guild_id: int, **kwargs):
    db = get_db()
    if not db:
        data = _json_read("antiraid_config")
        data[str(guild_id)] = {**data.get(str(guild_id), {}), **kwargs}
        return _json_write("antiraid_config", data)
    try:
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
    except Exception:
        data = _json_read("antiraid_config")
        data[str(guild_id)] = {**data.get(str(guild_id), {}), **kwargs}
        _json_write("antiraid_config", data)

# ── Broadcast ─────────────────────────────────────────────────────────
def add_broadcast(guild_id: int, channel_ids: list, title: str,
                   message: str, sent_by: int = 0, sent_to: int = 0):
    db = get_db()
    if not db:
        data = _json_read("broadcast_history")
        if not isinstance(data, list):
            data = []
        data.insert(0, {"guild_id": guild_id, "channel_ids": channel_ids,
                         "title": title, "message": message,
                         "sent_by": sent_by, "sent_to": sent_to, "time": time.time()})
        return _json_write("broadcast_history", data)
    try:
        db.run("""
            INSERT INTO broadcast_history (guild_id, channel_ids, title, message, sent_by, sent_to)
            VALUES (:gid, :cids, :t, :m, :sb, :st)
        """, gid=guild_id,
             cids="{" + ",".join(str(c) for c in channel_ids) + "}",
             t=title, m=message, sb=sent_by, st=sent_to)
    except Exception:
        data = _json_read("broadcast_history")
        if not isinstance(data, list):
            data = []
        data.insert(0, {"guild_id": guild_id, "channel_ids": channel_ids,
                         "title": title, "message": message,
                         "sent_by": sent_by, "sent_to": sent_to, "time": time.time()})
        _json_write("broadcast_history", data)

def get_broadcast_history(guild_id: int, limit: int = 10) -> list:
    db = get_db()
    if not db:
        data = _json_read("broadcast_history")
        if not isinstance(data, list):
            return []
        filtered = [d for d in data if d.get("guild_id") == guild_id]
        return filtered[:limit]
    try:
        rows = db.run("""
            SELECT id, channel_ids, title, message, sent_to, created_at
            FROM broadcast_history WHERE guild_id = :gid
            ORDER BY created_at DESC LIMIT :lim
        """, gid=guild_id, lim=limit)
        cols = ["id", "channel_ids", "title", "message", "sent_to", "time"]
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []

# ── Tickets ───────────────────────────────────────────────────────────
def create_ticket(guild_id: int, user_id: int, category: str = "general") -> Optional[dict]:
    db = get_db()
    if not db:
        data = _json_read("tickets")
        if not isinstance(data, list):
            data = []
        tid = int(time.time())
        ticket = {"id": tid, "guild_id": guild_id, "user_id": user_id,
                   "category": category, "status": "open"}
        data.insert(0, ticket)
        _json_write("tickets", data)
        return ticket
    try:
        db.run("""
            INSERT INTO tickets (guild_id, user_id, category)
            VALUES (:gid, :uid, :cat)
        """, gid=guild_id, uid=user_id, cat=category)
        row = db.run("SELECT * FROM tickets WHERE id = LASTVAL()")
        cols = [c["name"] for c in db.columns]
        return dict(zip(cols, row[0]))
    except Exception:
        return None

def close_ticket(ticket_id: int, closed_by: int = 0):
    db = get_db()
    if not db:
        data = _json_read("tickets")
        if not isinstance(data, list):
            return
        for t in data:
            if t.get("id") == ticket_id:
                t["status"] = "closed"
                t["closed_by"] = closed_by
                break
        return _json_write("tickets", data)
    try:
        db.run("""
            UPDATE tickets SET status = 'closed', closed_at = NOW(), closed_by = :cb
            WHERE id = :tid
        """, tid=ticket_id, cb=closed_by)
    except Exception:
        pass

def get_user_ticket(guild_id: int, user_id: int) -> Optional[dict]:
    db = get_db()
    if not db:
        data = _json_read("tickets")
        if not isinstance(data, list):
            return None
        for t in data:
            if t.get("guild_id") == guild_id and t.get("user_id") == user_id and t.get("status") == "open":
                return t
        return None
    try:
        row = db.run("""
            SELECT * FROM tickets WHERE guild_id = :gid AND user_id = :uid AND status = 'open'
            LIMIT 1
        """, gid=guild_id, uid=user_id)
        if not row:
            return None
        cols = [c["name"] for c in db.columns]
        return dict(zip(cols, row[0]))
    except Exception:
        return None

def get_all_tickets(guild_id: int, status: str = None) -> list:
    db = get_db()
    if not db:
        data = _json_read("tickets")
        if not isinstance(data, list):
            return []
        filtered = [t for t in data if t.get("guild_id") == guild_id]
        if status:
            filtered = [t for t in filtered if t.get("status") == status]
        return filtered
    try:
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
    except Exception:
        return []

# ── Warns ─────────────────────────────────────────────────────────────
def add_warn(guild_id: int, user_id: int, moderator_id: int = 0, reason: str = ""):
    db = get_db()
    if not db:
        data = _json_read("warns")
        if not isinstance(data, list):
            data = []
        data.insert(0, {"guild_id": guild_id, "user_id": user_id,
                         "moderator_id": moderator_id, "reason": reason,
                         "time": time.time()})
        return _json_write("warns", data)
    try:
        db.run("""
            INSERT INTO warns (guild_id, user_id, moderator_id, reason)
            VALUES (:gid, :uid, :mid, :r)
        """, gid=guild_id, uid=user_id, mid=moderator_id, r=reason)
    except Exception:
        data = _json_read("warns")
        data.insert(0, {"guild_id": guild_id, "user_id": user_id,
                         "moderator_id": moderator_id, "reason": reason,
                         "time": time.time()})
        _json_write("warns", data)

def get_warns(guild_id: int, user_id: int) -> list:
    db = get_db()
    if not db:
        data = _json_read("warns")
        if not isinstance(data, list):
            return []
        return [d for d in data if d.get("guild_id") == guild_id and d.get("user_id") == user_id]
    try:
        rows = db.run("""
            SELECT id, reason, moderator_id, created_at FROM warns
            WHERE guild_id = :gid AND user_id = :uid
            ORDER BY created_at DESC
        """, gid=guild_id, uid=user_id)
        cols = ["id", "reason", "moderator_id", "time"]
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []

def clear_warns(guild_id: int, user_id: int):
    db = get_db()
    if not db:
        data = _json_read("warns")
        if not isinstance(data, list):
            return
        data = [d for d in data if not (d.get("guild_id") == guild_id and d.get("user_id") == user_id)]
        return _json_write("warns", data)
    try:
        db.run("DELETE FROM warns WHERE guild_id = :gid AND user_id = :uid",
                gid=guild_id, uid=user_id)
    except Exception:
        pass

# ── Welcome History ───────────────────────────────────────────────────
def add_welcome(guild_id: int, user_id: int):
    db = get_db()
    if not db:
        data = _json_read("welcome_history")
        if not isinstance(data, list):
            data = []
        data.insert(0, {"guild_id": guild_id, "user_id": user_id, "time": time.time()})
        return _json_write("welcome_history", data)
    try:
        db.run("INSERT INTO welcome_history (guild_id, user_id) VALUES (:gid, :uid)",
                gid=guild_id, uid=user_id)
    except Exception:
        pass

def get_welcome_count(guild_id: int) -> int:
    db = get_db()
    if not db:
        data = _json_read("welcome_history")
        if not isinstance(data, list):
            return 0
        return len([d for d in data if d.get("guild_id") == guild_id])
    try:
        row = db.run("SELECT COUNT(*) FROM welcome_history WHERE guild_id = :gid",
                      gid=guild_id)
        return row[0][0] if row else 0
    except Exception:
        return 0

# ── Init first-time data ──────────────────────────────────────────────
def init_defaults():
    """Set default stats if they don't exist"""
    db = get_db()
    if not db:
        return
    try:
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
    except Exception:
        pass
