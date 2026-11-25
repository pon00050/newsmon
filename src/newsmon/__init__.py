"""newsmon: foreign-news desk monitoring. O1 (deterministic, no AI provider) is a complete operating mode."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("newsmon")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+src"
