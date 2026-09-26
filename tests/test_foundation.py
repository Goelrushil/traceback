from traceback_core import __version__
from traceback_core.config import settings


def test_foundation():
    assert __version__ == "0.1.0"
    assert settings.version == "0.1.0"
    assert settings.environment
    assert settings.log_level
