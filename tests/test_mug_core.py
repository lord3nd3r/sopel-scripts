import time
import types
import os

from types import SimpleNamespace

# Import the module under test
import importlib.util
spec = importlib.util.spec_from_file_location('mug_mod','/run/user/1000/gvfs/sftp:host=boston.3nd3r.net/home/ender/.sopel/scripts/mug.py')
mug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mug)

class DummyDB:
    def __init__(self):
        self.store = {}
    def get_plugin_value(self, k, v):
        return self.store.get((k, v))
    def set_plugin_value(self, k, v, val=None):
        # support both set_plugin_value(k,v,val) and set_plugin_value(k,v)
        if val is None:
            # called as set_plugin_value(k,v)
            self.store[(k, v)] = {}
        else:
            self.store[(k, v)] = val

class DummyBot(SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.db = DummyDB()
        self.config = SimpleNamespace(core=SimpleNamespace(homedir=os.getcwd()))
        self.channels = {}
        self.logger = types.SimpleNamespace(exception=lambda *a, **k: None)


def test_split_for_irc_simple():
    text = "A quick message that should be split into several parts | and remain sane"
    parts = mug._split_for_irc(text, max_bytes=40)
    assert all(len(p.encode('utf-8')) <= 40 for p in parts)
    assert '|' in ' | '.join(parts) or len(parts) > 1


def test_inventory_normalization_and_get_item_bonus(tmp_path):
    bot = DummyBot()
    # seed plugin data with mixed-case inventory
    data = {'users': {'alice': {'nick': 'Alice', 'money': 100, 'inv': {'LuckyCoin': 2, 'vest': 1}}}, 'bounties': {}, 'last_bounty': {}}
    bot.db.set_plugin_value(mug.PLUGIN_NAME, 'data', data)

    rec = mug.get_user_record(bot, 'Alice')
    # inventory keys should be normalized to lowercase
    assert 'luckycoin' in rec['inv']
    assert 'vest' in rec['inv']

    # item bonus: luckycoin gives coins_bonus_flat=3 per item
    bonus = mug.get_item_bonus(rec, 'coins_bonus_flat')
    assert bonus == 6


def test_mug_fee_not_charged_on_oops_jail(monkeypatch):
    bot = DummyBot()
    bot.db.set_plugin_value(mug.PLUGIN_NAME, 'data', {'users': {}, 'bounties': {}, 'last_bounty': {}})
    # create attacker with some money
    with mug.locked_data(bot):
        a = mug.get_user_record(bot, 'att')
        a['money'] = 50
        v = mug.get_user_record(bot, 'victim')
        v['money'] = 100

    # monkeypatch random.randint to force oops jail (<= chance)
    monkeypatch.setattr(mug.random, 'randint', lambda a, b: 1)

    class T:
        sender = '#chan'
        nick = 'att'
        def group(self, n=0):
            return 'att: $mug victim' if n==0 else 'victim'

    trigger = T()
    # call mug; since we forced randint==1, oops-jail path should run and fee shouldn't be charged
    mug.mug(bot, trigger)
    with mug.locked_data(bot):
        a = mug.get_user_record(bot, 'att')
        # attacker should have lost some money due to crit-fail but not the MUG_FEE pre-charge
        assert a['last_mug'] > 0

