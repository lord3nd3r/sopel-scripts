import random
import importlib.util
import os
import sys
import types

# Inject a minimal `sopel` stub into sys.modules so importing `weed.py` doesn't
# pick up the system-installed Sopel package (which interacts with pytest).
sopel_stub = types.ModuleType('sopel')

class _module:
    @staticmethod
    def commands(*names):
        return lambda f: f

    @staticmethod
    def example(*args, **kwargs):
        return lambda f: f

    @staticmethod
    def rule(*args, **kwargs):
        return lambda f: f


class _ColorsMeta(type):
    def __getattr__(cls, name):
        return name


class _Colors(metaclass=_ColorsMeta):
    pass


class _formatting:
    colors = _Colors

    @staticmethod
    def color(text, color):
        return text

    @staticmethod
    def bold(text):
        return text


sopel_stub.module = _module
sopel_stub.formatting = _formatting
sys.modules['sopel'] = sopel_stub

# Load weed.py by path to avoid package import issues during tests
TEST_DIR = os.path.dirname(__file__)
WEED_PATH = os.path.abspath(os.path.join(TEST_DIR, '..', 'weed.py'))
spec = importlib.util.spec_from_file_location('weed', WEED_PATH)
weed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(weed)


def test_format_remaining():
    assert weed._format_remaining(75) == '1m 15s'
    assert weed._format_remaining(45) == '45s'


def test_random_gift_in_list():
    random.seed(1)
    gift = random.choice(weed.WEED_GIFTS)
    assert gift in weed.WEED_GIFTS


def test_jay_mapping():
    assert 'jay' in weed.DATA
    assert 'joint' in weed.DATA
    jay_gifts, _, jay_final, _ = weed.DATA['jay']
    # Check that jay content contains 'jay' and none of the jay gifts say 'joint'
    assert any('jay' in g for g in jay_gifts)
    assert not any('joint' in g for g in jay_gifts)
    assert not any('joint' in m for m in jay_final)
    assert any('jay' in m for m in jay_final)


def test_doobie_mapping():
    assert 'doobie' in weed.DATA
    doobie_gifts, _, doobie_final, _ = weed.DATA['doobie']
    # Check that doobie content contains 'doobie' and none of the gifts/messages say 'joint'
    assert any('doobie' in g for g in doobie_gifts)
    assert not any('joint' in g for g in doobie_gifts)
    assert not any('joint' in m for m in doobie_final)
    assert any('doobie' in m for m in doobie_final)



