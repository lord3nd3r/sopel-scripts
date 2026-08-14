import importlib.util
import os
import sys
import tempfile
import types
import pytest

# Create minimal sopel stub modules
sopel_stub = types.ModuleType('sopel')
plugin = types.SimpleNamespace()
plugin.event = lambda *a, **k: (lambda f: f)
plugin.rule = lambda *a, **k: (lambda f: f)
plugin.priority = lambda *a, **k: (lambda f: f)
plugin.thread = lambda *a, **k: (lambda f: f)
plugin.interval = lambda *a, **k: (lambda f: f)
sopel_stub.plugin = plugin

config_mod = types.ModuleType('sopel.config')
types_mod = types.ModuleType('sopel.config.types')

class StaticSection:
    pass

class SimpleAttr:
    def __init__(self, name, default=None, **kwargs):
        self.name = name
        self.default = default

class ValidatedAttribute(SimpleAttr):
    pass

class ListAttribute(SimpleAttr):
    pass

types_mod.StaticSection = StaticSection
types_mod.ValidatedAttribute = ValidatedAttribute
types_mod.ListAttribute = ListAttribute

config_mod.types = types_mod
sopel_stub.config = config_mod

sys.modules['sopel'] = sopel_stub
sys.modules['sopel.config'] = config_mod
sys.modules['sopel.config.types'] = types_mod

# Load harambe.py
TEST_DIR = os.path.dirname(__file__)
FILE_PATH = os.path.abspath(os.path.join(TEST_DIR, '..', 'harambe.py'))
spec = importlib.util.spec_from_file_location('harambe', FILE_PATH)
harambe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harambe)


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    monkeypatch.setattr(harambe, '_DB_PATH', path)
    
    class DummyBot:
        pass
    
    harambe._init_db(DummyBot())
    yield path
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def test_ip_validation():
    assert harambe._is_valid_ip('127.0.0.1') is True
    assert harambe._is_valid_ip('8.8.8.8') is True
    assert harambe._is_valid_ip('2001:0db8:85a3:0000:0000:8a2e:0370:7334') is True
    assert harambe._is_valid_ip('::1') is True
    assert harambe._is_valid_ip('example.com') is False
    assert harambe._is_valid_ip('user!ident@host') is False
    assert harambe._is_valid_ip('') is False
    assert harambe._is_valid_ip(None) is False


def test_wildcard_to_sql():
    like, esc = harambe._wildcard_to_sql('test*')
    assert like == 'test%'
    assert esc == '\\'

    like, esc = harambe._wildcard_to_sql('user?123')
    assert like == 'user_123'

    like, esc = harambe._wildcard_to_sql('100%_pure')
    assert like == '100\\%\\_pure'


def test_db_init_and_indexes():
    with harambe._get_db() as conn:
        indexes = [row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
        assert 'idx_users_ip' in indexes
        assert 'idx_users_host' in indexes


def test_upsert_user_and_merge():
    # Insert new user
    harambe._upsert_user({
        'nick': 'Ender',
        'ident': 'ender',
        'host': 'boston.net',
        'ip': '1.2.3.4',
        'name': 'Ender Wiggin'
    })

    with harambe._get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE nick_lower = 'ender'").fetchone()
        assert row is not None
        assert row['nick'] == 'Ender'
        assert row['ip'] == '1.2.3.4'
        assert row['name'] == 'Ender Wiggin'

    # Update with partial data without clobbering existing fields
    harambe._upsert_user({
        'nick': 'Ender',
        'account': 'EnderAcct'
    })

    with harambe._get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE nick_lower = 'ender'").fetchone()
        assert row['ip'] == '1.2.3.4'
        assert row['account'] == 'EnderAcct'
        assert row['name'] == 'Ender Wiggin'


def test_search_and_glob_error_handling():
    harambe._upsert_user({
        'nick': 'Alice',
        'ident': 'alice',
        'host': 'wonderland.org',
        'ip': '10.0.0.1'
    })
    harambe._upsert_user({
        'nick': 'Bob',
        'ident': 'bob',
        'host': 'builder.org',
        'ip': '10.0.0.2'
    })

    # Normal case-insensitive search
    results = harambe._search('nick', 'ali*', case_sensitive=False, max_results=10)
    assert len(results) == 1
    assert results[0]['nick'] == 'Alice'

    # Normal case-sensitive search
    results_cs = harambe._search('nick', 'Ali*', case_sensitive=True, max_results=10)
    assert len(results_cs) == 1
    assert results_cs[0]['nick'] == 'Alice'

    results_cs_none = harambe._search('nick', 'ali*', case_sensitive=True, max_results=10)
    assert len(results_cs_none) == 0

    # Malformed GLOB pattern (unmatched bracket) should not raise sqlite3.OperationalError
    results_malformed = harambe._search('nick', '[ali', case_sensitive=True, max_results=10)
    assert results_malformed == []


def test_whois_channels_accumulation():
    # Simulate pending WHOIS
    with harambe._whois_lock:
        harambe._whois_pending['testuser'] = {'nick': 'TestUser'}

    class DummyTrigger:
        def __init__(self, text, args):
            self.text = text
            self.args = args

    # First channel line
    harambe.whois_channels(None, DummyTrigger('#chan1 #chan2', ['bot', 'TestUser', '#chan1 #chan2']))
    # Second channel line
    harambe.whois_channels(None, DummyTrigger('#chan3 #chan4', ['bot', 'TestUser', '#chan3 #chan4']))

    with harambe._whois_lock:
        data = harambe._whois_pending.pop('testuser')
        assert data['channels'] == '#chan1 #chan2 #chan3 #chan4'


def test_nickserv_notice_parsing():
    # Test Anope unregistered notice format "<nick> is not registered."
    query = harambe.NickServQuery('UnregUser')
    with harambe._ns_queries_lock:
        harambe._ns_queries['unreguser'] = query

    class TriggerNotice:
        nick = 'NickServ'
        def __init__(self, text):
            self.text = text
        def __str__(self):
            return self.text

    harambe.on_nickserv_notice(None, TriggerNotice('UnregUser is not registered.'))
    assert query.data['is_registered'] is False
    assert query.event.is_set()

    # Test Atheme unregistered notice format "Nick LordComac isn't registered."
    query2 = harambe.NickServQuery('LordComac')
    with harambe._ns_queries_lock:
        harambe._ns_queries['lordcomac'] = query2

    harambe.on_nickserv_notice(None, TriggerNotice("Nick LordComac isn't registered."))
    assert query2.data['is_registered'] is False
    assert query2.event.is_set()

    # Test Atheme registered info notice
    query3 = harambe.NickServQuery('RegUser')
    with harambe._ns_queries_lock:
        harambe._ns_queries['reguser'] = query3

    harambe.on_nickserv_notice(None, TriggerNotice('Information on RegUser (account RegUser):'))
    assert query3.data['is_registered'] is True
    harambe.on_nickserv_notice(None, TriggerNotice('Time registered: 2020-01-01 00:00:00 UTC'))
    assert query3.data['ns_registered'] == '2020-01-01 00:00:00 UTC'

    # Test Anope / InspIRCd registered info format with spaces before colons and End of INFO
    query4 = harambe.NickServQuery('End3r')
    with harambe._ns_queries_lock:
        harambe._ns_queries['end3r'] = query4

    harambe.on_nickserv_notice(None, TriggerNotice('Information on End3r (account End3r):'))
    harambe.on_nickserv_notice(None, TriggerNotice('Registered : Apr 14 18:22:15 2024 UTC (1 year, 122 days ago)'))
    harambe.on_nickserv_notice(None, TriggerNotice('Last seen : now'))
    harambe.on_nickserv_notice(None, TriggerNotice('E-mail : ender@3nd3r.net'))
    harambe.on_nickserv_notice(None, TriggerNotice('Options : Protected, Auto-op'))
    harambe.on_nickserv_notice(None, TriggerNotice('*** End of INFO ***'))

    assert query4.data['is_registered'] is True
    assert query4.data['ns_registered'] == 'Apr 14 18:22:15 2024 UTC (1 year, 122 days ago)'
    assert query4.data['ns_last_seen'] == 'now'
    assert query4.data['ns_email'] == 'ender@3nd3r.net'
    assert query4.data['ns_options'] == 'Protected, Auto-op'
    assert query4.event.is_set()

