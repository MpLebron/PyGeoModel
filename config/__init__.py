"""
Configuration loader for API keys.
Loads from config/api_keys.json, with fallback to environment variables.
"""
import os
import json
from pathlib import Path


def _load_config():
    """Load API keys from config file or environment variables."""
    config_path = Path(__file__).parent / "api_keys.json"

    config = {
        "openai": {"api_key": None, "base_url": "https://api.openai.com/v1"},
        "dify": {"api_key": None, "base_url": "https://api.dify.ai/v1"},
        "consensus": {"api_key": None}
    }

    # Try to load from config file
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                for key in config:
                    if key in file_config:
                        config[key].update(file_config[key])
        except (json.JSONDecodeError, IOError):
            pass

    # Environment variables override config file
    if os.environ.get("OPENAI_API_KEY"):
        config["openai"]["api_key"] = os.environ["OPENAI_API_KEY"]
    if os.environ.get("OPENAI_BASE_URL"):
        config["openai"]["base_url"] = os.environ["OPENAI_BASE_URL"]
    if os.environ.get("DIFY_API_KEY"):
        config["dify"]["api_key"] = os.environ["DIFY_API_KEY"]
    if os.environ.get("CONSENSUS_API_KEY"):
        config["consensus"]["api_key"] = os.environ["CONSENSUS_API_KEY"]

    return config


# Load config on module import
_config = _load_config()


def get_openai_config():
    """Get OpenAI API configuration."""
    return _config["openai"]["api_key"], _config["openai"]["base_url"]


def get_dify_config():
    """Get Dify API configuration."""
    return _config["dify"]["api_key"], _config["dify"]["base_url"]


def get_consensus_config():
    """Get Consensus API configuration."""
    return _config["consensus"]["api_key"]
