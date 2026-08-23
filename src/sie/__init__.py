"""SEO Intelligence Engine -- zero-paid-API website intelligence platform."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("seo-intelligence-engine")
except importlib.metadata.PackageNotFoundError:  # running from source, not installed
    __version__ = "0.0.0.dev0"
