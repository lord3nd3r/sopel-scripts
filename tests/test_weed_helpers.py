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


class _formatting:
    class colors:
        GREEN = 'GREEN'
        YELLOW = 'YELLOW'
        RED = 'RED'
        LIGHT_GREEN = 'LIGHT_GREEN'

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
