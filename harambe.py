# harambe.py — IRC user search service for Sopel
#
# Collects user data via WHOIS, CTCP VERSION, and oper-privileged WHO replies.
# Stores data in SQLite. Supports wildcard search across: nick, ident, host,
# vhost, ip, name, account, email, server, version, channels.
#
# Commands (via NOTICE to requester):
#   !help / !commands       — show help
#   !ping / !p              — liveness check
#   !search / !s <field> <pattern>   — case-insensitive wildcard search
#   !csearch / !cs <field> <pattern> — case-sensitive wildcard search
#   !ip <addr|nick>         — IP lookup / geo info
#
# Config (in sopel .cfg):
#   [harambe]
#   oper_name     = myoperaccount
#   oper_password = secret
#   access_channel = #3nd3r            ; users in this channel can search
#   access_list   = Nick1, Nick2       ; additional nicks (always allowed)
#   max_results   = 10                 ; max rows per search (default 10)

from __future__ import annotations

import fnmatch
import logging
import os
import re
import sqlite3
import threading
import time

import requests
from sopel import plugin
from sopel.config.types import StaticSection, ValidatedAttribute, ListAttribute

LOG = logging.getLogger(__name__)

# ─────────────────────────── config ─────────────────────────────────

class HarambeSection(StaticSection):
    oper_name     = ValidatedAttribute('oper_name',     default='')
    oper_password = ValidatedAttribute('oper_password', default='')
    access_channel = ValidatedAttribute('access_channel', default='')
    access_list   = ListAttribute('access_list', default=[])
    max_results   = ValidatedAttribute('max_results', default='10')


def configure(config):
    config.define_section('harambe', HarambeSection)
    config.harambe.configure_setting('oper_name',      'IRC oper account name')
    config.harambe.configure_setting('oper_password',  'IRC oper password')
    config.harambe.configure_setting('access_channel', 'Channel whose members can use search')
    config.harambe.configure_setting('access_list',    'Comma-separated nicks always allowed')
    config.harambe.configure_setting('max_results',    'Max results per search (default 10)')


def setup(bot):
    bot.config.define_section('harambe', HarambeSection)
    _init_db(bot)
    # Attempt to oper up immediately if credentials are set
    _oper_up(bot)
    LOG.info('harambe: plugin loaded')


def shutdown(bot):
    LOG.info('harambe: shutting down')


# ─────────────────────────── helpers ─────────────────────────────────

SEARCHABLE_FIELDS = ('nick', 'ident', 'host', 'vhost', 'ip', 'name',
                     'account', 'email', 'server', 'version', 'channels')

_DB_PATH = os.path.expanduser('~/.sopel/harambe.db')
_db_lock  = threading.Lock()

# Pending WHOIS state: nick_lower → dict of gathered fields
_whois_pending: dict[str, dict] = {}
_whois_lock = threading.Lock()

# Pending CTCP VERSION replies: nick_lower → timer
_ctcp_pending: dict[str, threading.Timer] = {}
_ctcp_lock = threading.Lock()

# True once the server confirms oper with 381 RPL_YOUREOPER
_is_oper = False


# NickServ INFO query state
class NickServQuery:
    def __init__(self, nick: str):
        self.nick = nick
        self.nick_lower = nick.lower()
        self.event = threading.Event()
        self.data = {
            'nick': nick,
            'ns_registered': None,
            'ns_last_seen': None,
            'ns_email': None,
            'ns_options': None,
            'is_registered': None,
        }

_ns_queries: dict[str, NickServQuery] = {}
_ns_queries_lock = threading.Lock()
_ns_current_nick: str | None = None
_ns_timer: threading.Timer | None = None
_ns_timer_lock = threading.Lock()


def _reset_ns_timer(q):
    global _ns_timer
    with _ns_timer_lock:
        if _ns_timer:
            _ns_timer.cancel()
        _ns_timer = threading.Timer(0.15, q.event.set)
        _ns_timer.start()


def _query_nickserv(bot, nick: str, timeout: float = 3.0) -> dict | None:
    nick_lower = nick.lower()
    query = NickServQuery(nick)

    with _ns_queries_lock:
        # Cancel/overwrite any existing query for this nick
        if nick_lower in _ns_queries:
            _ns_queries[nick_lower].event.set()
        _ns_queries[nick_lower] = query

    bot.write(['PRIVMSG', 'NickServ', f'INFO {nick}'])

    # Wait for the event to be set (either by the notice parser or a timeout)
    finished = query.event.wait(timeout)

    with _ns_queries_lock:
        _ns_queries.pop(nick_lower, None)
        global _ns_current_nick
        if _ns_current_nick == nick_lower:
            _ns_current_nick = None

    if finished and query.data['is_registered'] is not None:
        return query.data
    return None


def _get_conn():
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def _init_db(bot):
    with _db_lock, _get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                nick_lower  TEXT PRIMARY KEY,
                nick        TEXT,
                ident       TEXT,
                host        TEXT,
                vhost       TEXT,
                ip          TEXT,
                name        TEXT,
                account     TEXT,
                email       TEXT,
                server      TEXT,
                version     TEXT,
                channels    TEXT,
                last_seen   INTEGER
            )
        ''')
        # Check if NickServ columns exist, if not add them
        cursor = conn.execute('PRAGMA table_info(users)')
        columns = [row['name'] for row in cursor.fetchall()]

        new_cols = {
            'ns_registered': 'TEXT',
            'ns_last_seen': 'TEXT',
            'ns_email': 'TEXT',
            'ns_options': 'TEXT'
        }
        for col_name, col_type in new_cols.items():
            if col_name not in columns:
                conn.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
                LOG.info('harambe: added column %s to users table', col_name)

    LOG.info('harambe: database ready at %s', _DB_PATH)


def _upsert_user(data: dict):
    """Insert or update a user record, skipping None values (don't overwrite known data with None)."""
    nick_lower = data.get('nick_lower') or (data.get('nick') or '').lower()
    if not nick_lower:
        return

    with _db_lock, _get_conn() as conn:
        # Fetch existing row
        existing = conn.execute(
            'SELECT * FROM users WHERE nick_lower = ?', (nick_lower,)
        ).fetchone()

        merged = {
            'nick_lower': nick_lower,
            'nick':      data.get('nick'),
            'ident':     data.get('ident'),
            'host':      data.get('host'),
            'vhost':     data.get('vhost'),
            'ip':        data.get('ip'),
            'name':      data.get('name'),
            'account':   data.get('account'),
            'email':     data.get('email'),
            'server':    data.get('server'),
            'version':   data.get('version'),
            'channels':  data.get('channels'),
            'last_seen': data.get('last_seen', int(time.time())),
            'ns_registered': data.get('ns_registered'),
            'ns_last_seen':  data.get('ns_last_seen'),
            'ns_email':      data.get('ns_email'),
            'ns_options':    data.get('ns_options'),
        }

        if existing:
            # Prefer incoming non-None values, fallback to existing
            for k in merged:
                if merged[k] is None:
                    try:
                        merged[k] = existing[k]
                    except IndexError:
                        # In case columns weren't in existing row yet
                        merged[k] = None

        conn.execute('''
            INSERT INTO users
                (nick_lower, nick, ident, host, vhost, ip, name, account,
                 email, server, version, channels, last_seen,
                 ns_registered, ns_last_seen, ns_email, ns_options)
            VALUES
                (:nick_lower, :nick, :ident, :host, :vhost, :ip, :name, :account,
                 :email, :server, :version, :channels, :last_seen,
                 :ns_registered, :ns_last_seen, :ns_email, :ns_options)
            ON CONFLICT(nick_lower) DO UPDATE SET
                nick     = COALESCE(:nick,    nick),
                ident    = COALESCE(:ident,   ident),
                host     = COALESCE(:host,    host),
                vhost    = COALESCE(:vhost,   vhost),
                ip       = COALESCE(:ip,      ip),
                name     = COALESCE(:name,    name),
                account  = COALESCE(:account, account),
                email    = COALESCE(:email,   email),
                server   = COALESCE(:server,  server),
                version  = COALESCE(:version, version),
                channels = COALESCE(:channels, channels),
                last_seen = :last_seen,
                ns_registered = COALESCE(:ns_registered, ns_registered),
                ns_last_seen  = COALESCE(:ns_last_seen,  ns_last_seen),
                ns_email      = COALESCE(:ns_email,      ns_email),
                ns_options    = COALESCE(:ns_options,    ns_options)
        ''', merged)


def _oper_up(bot):
    """Send OPER command if credentials are configured."""
    try:
        name = bot.config.harambe.oper_name
        pw   = bot.config.harambe.oper_password
    except Exception:
        return
    if name and pw:
        bot.write(['OPER', name, pw])
        LOG.info('harambe: sent OPER %s', name)


def _is_authorized(bot, trigger) -> bool:
    """
    Returns True if the requester is allowed to use search commands.
    Allowed if:
      - Their nick is in the access_list config, OR
      - They are present in the configured access_channel
    """
    try:
        access_list    = [n.strip().lower() for n in bot.config.harambe.access_list]
        access_channel = (bot.config.harambe.access_channel or '').strip().lower()
    except Exception:
        return False

    nick_lower = str(trigger.nick).lower()

    if nick_lower in access_list:
        return True

    if access_channel:
        chan_obj = bot.channels.get(access_channel)
        if chan_obj and nick_lower in [u.lower() for u in chan_obj.users]:
            return True

    return False


def _wildcard_to_sql(pattern: str) -> tuple[str, str]:
    """
    Convert an IRC-style wildcard pattern (* and ?) into a SQL LIKE expression.
    Returns (like_pattern, escape_char).
    Escapes literal % and _ with backslash, then maps * → % and ? → _.
    """
    escaped = pattern.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    like    = escaped.replace('*', '%').replace('?', '_')
    return like, '\\'


def _row_to_str(row, exclude_fields: set | None = None) -> str:
    """Format a DB row as a Harambe-style result string."""
    nick    = row['nick']    or row['nick_lower']
    ident   = row['ident']   or '~unknown'
    host    = row['host']    or '*'
    parts   = [f'{nick}!{ident}@{host}']
    skip    = exclude_fields or set()

    for field in ('vhost', 'name', 'ip', 'server', 'account', 'version', 'email', 'channels'):
        if field in skip:
            continue
        val = row[field]
        if val:
            parts.append(f'[{field}={val}]')

    return ' '.join(parts)


def _search(field: str, pattern: str, case_sensitive: bool, max_results: int):
    """Run a wildcard search against the DB. Returns list of Row objects."""
    if field not in SEARCHABLE_FIELDS:
        return None  # invalid field

    like, esc = _wildcard_to_sql(pattern)
    col = field  # field name is validated — safe to interpolate

    if case_sensitive:
        # SQLite LIKE is case-insensitive by default; use GLOB for case sensitivity
        # but GLOB uses * and ? natively so we convert back
        glob_pat = pattern  # keep original wildcards; GLOB uses * and ?
        sql  = f'SELECT * FROM users WHERE {col} GLOB ? LIMIT ?'
        with _db_lock, _get_conn() as conn:
            rows = conn.execute(sql, (glob_pat, max_results + 1)).fetchall()
    else:
        sql  = f'SELECT * FROM users WHERE {col} LIKE ? ESCAPE ? LIMIT ?'
        with _db_lock, _get_conn() as conn:
            rows = conn.execute(sql, (like, esc, max_results + 1)).fetchall()

    return rows


# ─────────────────────────── WHOIS collection ────────────────────────

def _start_whois(bot, nick: str):
    """Issue a WHOIS for a nick and start collecting replies."""
    nick_lower = nick.lower()
    with _whois_lock:
        _whois_pending[nick_lower] = {'nick': nick}
    bot.write(['WHOIS', nick, nick])  # double nick = include idle time


def _finalize_whois(bot, nick_lower: str):
    """Called when WHOIS is complete (318) — flush data to DB."""
    with _whois_lock:
        data = _whois_pending.pop(nick_lower, None)
    if data:
        _upsert_user(data)
        # Only probe for CTCP VERSION if we have confirmed oper AND credentials are configured
        oper_configured = bool((bot.config.harambe.oper_name or '').strip())
        if _is_oper and oper_configured:
            nick = data.get('nick', nick_lower)
            _request_version(bot, nick)


def _request_version(bot, nick: str):
    """Send CTCP VERSION request and set a timeout to give up."""
    nick_lower = nick.lower()

    def _timeout():
        with _ctcp_lock:
            _ctcp_pending.pop(nick_lower, None)
        LOG.debug('harambe: CTCP VERSION timeout for %s', nick)

    timer = threading.Timer(30, _timeout)
    with _ctcp_lock:
        old = _ctcp_pending.pop(nick_lower, None)
        if old:
            old.cancel()
        _ctcp_pending[nick_lower] = timer

    timer.start()
    bot.write(['PRIVMSG', nick, '\x01VERSION\x01'])


# ─────────────────────────── IRC event handlers ───────────────────────

@plugin.rule('.*')
@plugin.event('JOIN')
@plugin.priority('low')
@plugin.thread(True)
def on_join(bot, trigger):
    """When a user joins the access channel, queue a WHOIS for them (oper only)."""
    if not _is_oper:
        return
    nick = str(trigger.nick)
    if nick.lower() == bot.nick.lower():
        return
    # Only collect data from the configured access channel
    access_channel = (bot.config.harambe.access_channel or '').strip().lower()
    if str(trigger.sender).lower() != access_channel:
        return
    _start_whois(bot, nick)


@plugin.rule('.*')
@plugin.event('001')  # RPL_WELCOME — we connected
@plugin.priority('low')
@plugin.thread(True)
def on_welcome(bot, trigger):
    """Re-send OPER after connecting (in case the bot restarts mid-session)."""
    global _is_oper
    _is_oper = False  # reset until server confirms with 381
    _oper_up(bot)


@plugin.rule('.*')
@plugin.event('381')  # RPL_YOUREOPER — server confirmed oper
@plugin.priority('low')
@plugin.thread(True)
def on_youreoper(bot, trigger):
    """Set oper flag when the server confirms oper status (381)."""
    global _is_oper
    _is_oper = True
    LOG.info('harambe: oper confirmed — CTCP VERSION collection enabled')


# ── WHOIS reply numerics ──────────────────────────────────────────────

@plugin.rule('.*')
@plugin.event('311')  # RPL_WHOISUSER  :nick!user@host * :realname
@plugin.priority('low')
@plugin.thread(True)
def whois_user(bot, trigger):
    # args: botnick target_nick ident host * :realname
    args = trigger.args
    if len(args) < 4:
        return
    nick_lower = args[1].lower()
    with _whois_lock:
        if nick_lower not in _whois_pending:
            return
        _whois_pending[nick_lower].update({
            'nick':  args[1],
            'ident': args[2],
            'host':  args[3],
            'name':  trigger.group(0) or args[-1] if trigger.group(0) else args[-1],
        })


@plugin.rule('.*')
@plugin.event('312')  # RPL_WHOISSERVER  :nick server :info
@plugin.priority('low')
@plugin.thread(True)
def whois_server(bot, trigger):
    args = trigger.args
    if len(args) < 3:
        return
    nick_lower = args[1].lower()
    with _whois_lock:
        if nick_lower in _whois_pending:
            _whois_pending[nick_lower]['server'] = args[2]


@plugin.rule('.*')
@plugin.event('319')  # RPL_WHOISCHANNELS  :nick :channels
@plugin.priority('low')
@plugin.thread(True)
def whois_channels(bot, trigger):
    args = trigger.args
    if len(args) < 2:
        return
    nick_lower = args[1].lower()
    raw_chans  = (trigger.group(0) or args[-1]).strip()
    with _whois_lock:
        if nick_lower in _whois_pending:
            _whois_pending[nick_lower]['channels'] = raw_chans


@plugin.rule('.*')
@plugin.event('330')  # RPL_WHOISACCOUNT  :nick account :is logged in as
@plugin.priority('low')
@plugin.thread(True)
def whois_account(bot, trigger):
    args = trigger.args
    if len(args) < 3:
        return
    nick_lower = args[1].lower()
    with _whois_lock:
        if nick_lower in _whois_pending:
            _whois_pending[nick_lower]['account'] = args[2]


@plugin.rule('.*')
@plugin.event('338')  # RPL_WHOISACTUALLY  :nick real@host :actual IP  (oper-visible)
@plugin.priority('low')
@plugin.thread(True)
def whois_actually(bot, trigger):
    """338 gives us the real IP when the bot has oper."""
    args = trigger.args
    if len(args) < 3:
        return
    nick_lower = args[1].lower()
    # args[2] may be ip or user@host; args[3] if present is the IP
    real_ip = args[3] if len(args) > 3 else args[2]
    # Strip any user@ prefix
    if '@' in real_ip:
        real_ip = real_ip.split('@', 1)[1]
    with _whois_lock:
        if nick_lower in _whois_pending:
            _whois_pending[nick_lower]['ip'] = real_ip


@plugin.rule('.*')
@plugin.event('671')  # RPL_WHOISSECURE  :nick :is using a secure connection
@plugin.priority('low')
def whois_secure(bot, trigger):
    pass  # We don't need to track this but don't let it be ignored noisily


@plugin.rule('.*')
@plugin.event('318')  # RPL_ENDOFWHOIS
@plugin.priority('low')
@plugin.thread(True)
def whois_end(bot, trigger):
    args = trigger.args
    if len(args) < 2:
        return
    nick_lower = args[1].lower()
    _finalize_whois(bot, nick_lower)


@plugin.rule('.*')
@plugin.event('320')  # RPL_WHOISSPECIAL (email on some networks like Rizon)
@plugin.priority('low')
@plugin.thread(True)
def whois_special(bot, trigger):
    """Rizon sends email in 320 as 'is identified for this nick (email@addr)'."""
    args = trigger.args
    if len(args) < 2:
        return
    nick_lower = args[1].lower()
    text = (trigger.group(0) or '').strip()
    # Try to extract an email address from the text
    m = re.search(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', text)
    if m:
        with _whois_lock:
            if nick_lower in _whois_pending:
                _whois_pending[nick_lower]['email'] = m.group(0)


# ── CTCP VERSION reply ────────────────────────────────────────────────

@plugin.rule('\x01VERSION (.*)\x01')
@plugin.priority('low')
@plugin.thread(True)
def ctcp_version_reply(bot, trigger):
    """Catch incoming CTCP VERSION replies."""
    nick_lower = str(trigger.nick).lower()

    with _ctcp_lock:
        timer = _ctcp_pending.pop(nick_lower, None)
    if timer:
        timer.cancel()

    version = trigger.group(1) or ''
    _upsert_user({'nick': str(trigger.nick), 'version': version.strip()})
    LOG.debug('harambe: VERSION from %s: %s', trigger.nick, version)


# ── Track vhost changes (396) ─────────────────────────────────────────

@plugin.rule('.*')
@plugin.event('396')  # RPL_YOURHOSTIS / vhost applied
@plugin.priority('low')
@plugin.thread(True)
def on_vhost_set(bot, trigger):
    """396 is sent to a user when their vhost is applied. Also seen in WHOIS."""
    args = trigger.args
    if len(args) < 2:
        return
    # 396 target vhost :is now your displayed host
    nick_lower = args[0].lower()  # usually the target (or botnick for self)
    vhost = args[1]
    _upsert_user({'nick': args[0], 'vhost': vhost})


# ── NICK changes — update DB ──────────────────────────────────────────

@plugin.rule('.*')
@plugin.event('NICK')
@plugin.priority('low')
@plugin.thread(True)
def on_nick_change(bot, trigger):
    """When a user changes nick, create/link a new DB entry for the new nick."""
    old_nick = str(trigger.nick)
    new_nick  = str(trigger.args[0]) if trigger.args else ''
    if not new_nick or old_nick.lower() == bot.nick.lower():
        return

    # Copy old record to new nick then re-WHOIS
    with _db_lock, _get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM users WHERE nick_lower = ?', (old_nick.lower(),)
        ).fetchone()

    if row:
        data = dict(row)
        data['nick']      = new_nick
        data['nick_lower'] = new_nick.lower()
        _upsert_user(data)

    _start_whois(bot, new_nick)


# ── NickServ notice parser ────────────────────────────────────────────

@plugin.rule('.*')
@plugin.event('NOTICE')
@plugin.priority('low')
@plugin.thread(True)
def on_nickserv_notice(bot, trigger):
    """Parse incoming NickServ INFO notices."""
    # Only interested in NickServ
    if str(trigger.nick).lower() != 'nickserv':
        return

    text = (trigger.group(0) or '').strip()
    if not text:
        return

    global _ns_current_nick

    # Clean formatting/colors
    text_clean = re.sub(r'\x03\d{0,2}|\x02|\x0f|\x16|\x1f', '', text)

    # Check for "isn't registered" or "is not registered"
    # e.g., "Nick LordComac isn't registered." or "Nick LordComac is not registered."
    m_not_reg = re.match(r'^Nick\s+(\S+)\s+(?:isn\'t|is\s+not)\s+registered', text_clean, re.IGNORECASE)
    if m_not_reg:
        target_nick = m_not_reg.group(1).lower()
        with _ns_queries_lock:
            if target_nick in _ns_queries:
                q = _ns_queries[target_nick]
                q.data['is_registered'] = False
                q.event.set()
        return

    # Check for "<nick> is <something>"
    m_start = re.match(r'^(\S+)\s+is\s+', text_clean)
    if m_start:
        target_nick = m_start.group(1).lower()
        with _ns_queries_lock:
            if target_nick in _ns_queries:
                _ns_current_nick = target_nick
                _ns_queries[target_nick].data['is_registered'] = True
                _reset_ns_timer(_ns_queries[target_nick])
                return

    # If parsing a current active nick
    if _ns_current_nick:
        with _ns_queries_lock:
            if _ns_current_nick not in _ns_queries:
                _ns_current_nick = None
                return
            q = _ns_queries[_ns_current_nick]

        # Parse fields
        m_reg = re.search(r'Time registered:\s*(.+)', text_clean, re.IGNORECASE)
        if m_reg:
            q.data['ns_registered'] = m_reg.group(1).strip()
            _reset_ns_timer(q)
            return

        m_seen = re.search(r'Last seen time:\s*(.+)', text_clean, re.IGNORECASE)
        if m_seen:
            q.data['ns_last_seen'] = m_seen.group(1).strip()
            _reset_ns_timer(q)
            return

        m_email = re.search(r'E-mail address:\s*(.+)', text_clean, re.IGNORECASE)
        if m_email:
            q.data['ns_email'] = m_email.group(1).strip()
            _reset_ns_timer(q)
            return

        m_opts = re.search(r'Options:\s*(.+)', text_clean, re.IGNORECASE)
        if m_opts:
            q.data['ns_options'] = m_opts.group(1).strip()
            _reset_ns_timer(q)
            return

        # Any other line for this nick resets the silence timer to ensure we capture all lines
        _reset_ns_timer(q)



# ─────────────────────────── access control ──────────────────────────

def _reply(bot, dest: str, text: str):
    """Send a message to a channel (or nick if in PM)."""
    bot.say(text, dest)


# ─────────────────────────── commands ────────────────────────────────

# Harambe listens for !commands in PM — trigger on any PRIVMSG matching !<cmd>
# We use a catch-all rule on PRIVMSGs and dispatch manually so we can use
# ! as the prefix without changing the bot's global prefix.

_CMD_RE = re.compile(
    r'^!(?P<cmd>help|commands|ping|p|search|s|csearch|cs|ip|clones|info|last|count|ccount|stats)\s*(?P<rest>.*)$',
    re.IGNORECASE
)


@plugin.rule(r'^!(?:help|commands|ping|p|search|s|csearch|cs|ip|clones|info|last|count|ccount|stats).*')
@plugin.priority('low')
@plugin.thread(True)
def harambe_dispatch(bot, trigger):
    """Dispatch all Harambe ! commands."""
    raw = (trigger.group(0) or '').strip()
    m = _CMD_RE.match(raw)
    if not m:
        return

    # Only respond in the configured access_channel — ignore everything else
    access_channel = (bot.config.harambe.access_channel or '').strip().lower()
    if str(trigger.sender).lower() != access_channel:
        return

    nick    = str(trigger.nick)
    dest    = str(trigger.sender)  # channel name
    cmd     = m.group('cmd').lower()
    rest    = m.group('rest').strip()

    if cmd in ('help', 'commands'):
        _cmd_help(bot, nick)  # send help via PM to the requester
        return

    if cmd in ('ping', 'p'):
        _reply(bot, dest, 'PONG! I am alive and watching.')
        return

    # All search commands require authorization
    if not _is_authorized(bot, trigger):
        _reply(bot, dest, 'Access denied. You are not authorized to use Harambe.')
        return

    if cmd in ('search', 's'):
        _cmd_search(bot, dest, rest, case_sensitive=False)
    elif cmd in ('csearch', 'cs'):
        _cmd_search(bot, dest, rest, case_sensitive=True)
    elif cmd == 'ip':
        _cmd_ip(bot, dest, rest)
    elif cmd == 'clones':
        _cmd_clones(bot, dest, rest)
    elif cmd == 'info':
        _cmd_info(bot, dest, rest)
    elif cmd == 'last':
        _cmd_last(bot, dest, rest)
    elif cmd in ('count', 'ccount'):
        _cmd_count(bot, dest, rest, case_sensitive=(cmd == 'ccount'))
    elif cmd == 'stats':
        _cmd_stats(bot, dest)


def _cmd_help(bot, dest: str):
    lines = [
        'Harambe user search — fields: nick ident host vhost ip name account email server version channels',
        'Wildcards: * = any chars, ? = one char  |  Example: !s nick ex*ple  or  !s host *.example.com',
        '!search <field> <pattern>  (!s)  — case-insensitive search',
        '!csearch <field> <pattern> (!cs) — case-sensitive search',
        '!ip <address|nick>               — geo lookup for an IP, or look up a nick\'s IP',
        '!clones <nick|ip>                — find all nicks sharing the same IP or host/vhost',
        '!info <nick>                     — retrieve full info report (includes live NickServ query)',
        '!last <nick>                     — check when the user was last seen',
        '!count/!ccount <field> <pattern> — count matching records (case-insensitive/sensitive)',
        '!stats                           — show database metrics',
        '!ping (!p)                       — liveness check',
        '!help (!commands)                — this message',
    ]
    for line in lines:
        _reply(bot, dest, line)


def _cmd_search(bot, dest: str, rest: str, case_sensitive: bool):
    """Handle !search / !s / !csearch / !cs."""
    # Parse flags like -version, -email, etc. to exclude fields from output
    exclude_fields = set()
    tokens = rest.split()
    clean_tokens = []
    for tok in tokens:
        if tok.startswith('-') and tok[1:].lower() in SEARCHABLE_FIELDS:
            exclude_fields.add(tok[1:].lower())
        else:
            clean_tokens.append(tok)

    rest = ' '.join(clean_tokens)
    parts = rest.split(None, 1)
    if len(parts) < 2:
        _reply(bot, dest, 'Usage: !s <field> <pattern> [-version]  (fields: nick ident host vhost ip name account email server version channels)')
        return

    field   = parts[0].lower()
    pattern = parts[1]

    if field not in SEARCHABLE_FIELDS:
        _reply(bot, dest,
                f'Unknown field \'{field}\'. Valid fields: {" ".join(SEARCHABLE_FIELDS)}')
        return

    try:
        max_results = int(bot.config.harambe.max_results)
    except Exception:
        max_results = 10

    rows = _search(field, pattern, case_sensitive, max_results)

    if rows is None:
        _reply(bot, dest, f'Invalid field: {field}')
        return

    if not rows:
        _reply(bot, dest, 'No results')
        return

    truncated = len(rows) > max_results
    for i, row in enumerate(rows[:max_results], start=1):
        _reply(bot, dest, f'{i}: {_row_to_str(row, exclude_fields=exclude_fields)}')

    if truncated:
        _reply(bot, dest, f'Results truncated at {max_results}. Refine your search.')
    else:
        _reply(bot, dest, 'End of results')


def _cmd_ip(bot, dest: str, rest: str):
    """Handle !ip — geo lookup for an IP address, CIDR prefix, or nick."""
    target = rest.strip()
    if not target:
        _reply(bot, dest, 'Usage: !ip <address|nick>')
        return

    # Check if it looks like a nick (no dots, colons, or slashes) and look up in DB
    if not re.search(r'[.:/*?]', target):
        # Treat as a nick — look up their IP
        with _db_lock, _get_conn() as conn:
            row = conn.execute(
                'SELECT ip, nick FROM users WHERE nick_lower = ?',
                (target.lower(),)
            ).fetchone()
        if row and row['ip']:
            ip_target = row['ip']
            _reply(bot, dest, f'ip: {ip_target}')
        elif row:
            _reply(bot, dest, f'{target} is known but IP is not available.')
            return
        else:
            _reply(bot, dest, f'No record found for nick: {target}')
            return
    else:
        ip_target = target

    # Geo lookup via ipinfo.io (matches original Harambe output)
    try:
        resp = requests.get(
            f'https://ipinfo.io/{ip_target}/json',
            timeout=5,
        )
        data = resp.json()
    except Exception as e:
        _reply(bot, dest, f'IP lookup failed: {e}')
        return

    if 'error' in data:
        _reply(bot, dest, f'Lookup failed: {data["error"].get("message", "unknown error")}')
        return

    # Output each field on its own line, matching original Harambe format
    fields = [
        ('ip',       data.get('ip', ip_target)),
        ('city',     data.get('city')),
        ('region',   data.get('region')),
        ('country',  data.get('country')),
        ('loc',      data.get('loc')),
        ('org',      data.get('org')),
        ('postal',   data.get('postal')),
        ('timezone', data.get('timezone')),
    ]
    for name, val in fields:
        if val:
            _reply(bot, dest, f'{name}: {val}')


def _cmd_clones(bot, dest: str, rest: str):
    """Handle !clones — find all nicks sharing the same IP or host."""
    target = rest.strip()
    if not target:
        _reply(bot, dest, 'Usage: !clones <nick|ip>')
        return

    # Check if target is an IP (contains dots or colons)
    is_ip = bool(re.search(r'[.:]', target))

    ip_to_search = None
    host_to_search = None
    nick_searched = None

    if is_ip:
        ip_to_search = target
    else:
        # Treat as nick, look up in DB
        with _db_lock, _get_conn() as conn:
            row = conn.execute(
                'SELECT ip, host, vhost FROM users WHERE nick_lower = ?',
                (target.lower(),)
            ).fetchone()
        if row:
            nick_searched = target
            ip_to_search = row['ip']
            host_to_search = row['host']  # Use real host, not vhost
        else:
            _reply(bot, dest, f'No record found for nick: {target}')
            return

    if not ip_to_search and not host_to_search:
        _reply(bot, dest, f'No IP/host available for {target} to find clones.')
        return

    # Now search for other users with same IP or same real host (not vhost)
    with _db_lock, _get_conn() as conn:
        if ip_to_search and host_to_search:
            rows = conn.execute(
                'SELECT * FROM users WHERE (ip = ? OR host = ?) AND nick_lower != ?',
                (ip_to_search, host_to_search, (nick_searched or '').lower())
            ).fetchall()
        elif ip_to_search:
            rows = conn.execute(
                'SELECT * FROM users WHERE ip = ? AND nick_lower != ?',
                (ip_to_search, (nick_searched or '').lower())
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM users WHERE host = ? AND nick_lower != ?',
                (host_to_search, (nick_searched or '').lower())
            ).fetchall()

    if not rows:
        _reply(bot, dest, f'No clones found for {target}.')
        return

    criteria = f'IP {ip_to_search}' if ip_to_search else f'host {host_to_search}'
    if nick_searched:
        _reply(bot, dest, f'Clones for {nick_searched} (sharing {criteria}):')
    else:
        _reply(bot, dest, f'Clones sharing {criteria}:')

    for i, row in enumerate(rows, start=1):
        ns_info = ''
        if row['ns_registered']:
            ns_info = f' [registered={row["ns_registered"]}]'
        _reply(bot, dest, f'{i}: {_row_to_str(row)}{ns_info}')


def _cmd_info(bot, dest: str, rest: str):
    """Handle !info — full dump of WHOIS + NickServ info."""
    target = rest.strip()
    if not target:
        _reply(bot, dest, 'Usage: !info <nick>')
        return

    if re.search(r'[.:/*?]', target):
        _reply(bot, dest, 'Usage: !info <nick> (does not support wildcards or IP addresses)')
        return

    _reply(bot, dest, f'Querying NickServ for {target}...')
    ns_data = _query_nickserv(bot, target)

    if ns_data:
        _upsert_user(ns_data)

    with _db_lock, _get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM users WHERE nick_lower = ?',
            (target.lower(),)
        ).fetchone()

    if not row:
        _reply(bot, dest, f'No local database record for {target}.')
        return

    _reply(bot, dest, f'=== Intel Report for {row["nick"] or target} ===')
    userhost = f'{row["nick"]}!{row["ident"] or "~unknown"}@{row["host"] or "*"}'
    _reply(bot, dest, f'Userhost: {userhost}')
    if row['vhost']:
        _reply(bot, dest, f'Vhost:    {row["vhost"]}')
    if row['ip']:
        _reply(bot, dest, f'IP:       {row["ip"]}')
    if row['name']:
        _reply(bot, dest, f'Realname: {row["name"]}')
    if row['account']:
        _reply(bot, dest, f'Account:  {row["account"]}')
    if row['email']:
        _reply(bot, dest, f'Email:    {row["email"]}')
    if row['server']:
        _reply(bot, dest, f'Server:   {row["server"]}')
    if row['version']:
        _reply(bot, dest, f'Version:  {row["version"]}')
    if row['channels']:
        _reply(bot, dest, f'Channels: {row["channels"]}')
    if row['last_seen']:
        seen_str = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(row['last_seen']))
        _reply(bot, dest, f'Seen:     {seen_str}')

    if row['ns_registered']:
        _reply(bot, dest, f'NS Registered: {row["ns_registered"]}')
        if row['ns_last_seen']:
            _reply(bot, dest, f'NS Last Seen:  {row["ns_last_seen"]}')
        if row['ns_email']:
            _reply(bot, dest, f'NS Email:      {row["ns_email"]}')
        if row['ns_options']:
            _reply(bot, dest, f'NS Options:    {row["ns_options"]}')
    else:
        if ns_data and not ns_data['is_registered']:
            _reply(bot, dest, 'NickServ:      Nick is not registered.')
        else:
            _reply(bot, dest, 'NickServ:      No registration info.')


def _cmd_last(bot, dest: str, rest: str):
    """Handle !last — check when the nick was last seen by the bot."""
    target = rest.strip()
    if not target:
        _reply(bot, dest, 'Usage: !last <nick>')
        return

    with _db_lock, _get_conn() as conn:
        row = conn.execute(
            'SELECT nick, last_seen FROM users WHERE nick_lower = ?',
            (target.lower(),)
        ).fetchone()

    if not row or not row['last_seen']:
        _reply(bot, dest, f'No record of {target} ever being seen.')
    else:
        seen_time = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(row['last_seen']))
        diff = int(time.time()) - row['last_seen']
        if diff < 60:
            ago = f'{diff}s ago'
        elif diff < 3600:
            ago = f'{diff // 60}m ago'
        elif diff < 86400:
            ago = f'{diff // 3600}h ago'
        else:
            ago = f'{diff // 86400}d ago'
        _reply(bot, dest, f'{row["nick"]} was last seen on {seen_time} ({ago}).')


def _cmd_count(bot, dest: str, rest: str, case_sensitive: bool):
    """Handle !count and !ccount — return match count only."""
    parts = rest.split(None, 1)
    if len(parts) < 2:
        _reply(bot, dest, 'Usage: !count <field> <pattern>  (fields: nick ident host vhost ip name account email server version channels)')
        return

    field   = parts[0].lower()
    pattern = parts[1]

    if field not in SEARCHABLE_FIELDS:
        _reply(bot, dest, f'Unknown field \'{field}\'.')
        return

    like, esc = _wildcard_to_sql(pattern)
    col = field

    with _db_lock, _get_conn() as conn:
        if case_sensitive:
            row = conn.execute(
                f'SELECT COUNT(*) as cnt FROM users WHERE {col} GLOB ?',
                (pattern,)
            ).fetchone()
        else:
            row = conn.execute(
                f'SELECT COUNT(*) as cnt FROM users WHERE {col} LIKE ? ESCAPE ?',
                (like, esc)
            ).fetchone()

    count = row['cnt'] if row else 0
    _reply(bot, dest, f'Found {count} matching records for {field} = {pattern}')


def _cmd_stats(bot, dest: str):
    """Handle !stats — display database summary statistics."""
    with _db_lock, _get_conn() as conn:
        total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if not total:
            _reply(bot, dest, 'Database is empty.')
            return
        has_ip = conn.execute('SELECT COUNT(*) FROM users WHERE ip IS NOT NULL AND ip != ""').fetchone()[0]
        has_acct = conn.execute('SELECT COUNT(*) FROM users WHERE account IS NOT NULL AND account != ""').fetchone()[0]
        has_ver = conn.execute('SELECT COUNT(*) FROM users WHERE version IS NOT NULL AND version != ""').fetchone()[0]
        has_ns = conn.execute('SELECT COUNT(*) FROM users WHERE ns_registered IS NOT NULL').fetchone()[0]

    _reply(bot, dest, f'=== Harambe Database Statistics ===')
    _reply(bot, dest, f'Total users tracked: {total}')
    _reply(bot, dest, f'With IP address:     {has_ip} ({has_ip * 100 // total}%)')
    _reply(bot, dest, f'With registered NS:  {has_ns} ({has_ns * 100 // total}%)')
    _reply(bot, dest, f'With logged account: {has_acct} ({has_acct * 100 // total}%)')
    _reply(bot, dest, f'With client version: {has_ver} ({has_ver * 100 // total}%)')

