"""
Configuration Manager

Handles configuration loading from multiple sources with fallback priority:
1. Environment variables (highest priority)
2. Configuration file (config.json)
3. Default values (lowest priority)
"""

import json
import os
import logging
from typing import Any, Dict, Optional
from pathlib import Path

try:
    from .exceptions import AgiloftConfigError
except ImportError:
    from exceptions import AgiloftConfigError

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager with multiple source support."""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self._config_data: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from file and environment variables."""
        # Start with default configuration
        self._config_data = self._get_default_config()

        # Load from config file if it exists
        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                    self._merge_config(self._config_data, file_config)
                    logger.info(f"Loaded configuration from {config_path}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load config file {config_path}: {e}")
                raise AgiloftConfigError(f"Invalid configuration file {config_path}: {e}")
        else:
            logger.info(f"Config file {config_path} not found, using defaults and environment variables")

        # Override with environment variables
        self._load_from_environment()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "agiloft": {
                "base_url": "",
                "username": "",
                "password": "",
                "kb": "",
                "language": "en"
            }
        }

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _load_from_environment(self):
        """Load configuration from environment variables."""
        env_mappings = {
            "AGILOFT_BASE_URL": "agiloft.base_url",
            "AGILOFT_USERNAME": "agiloft.username",
            "AGILOFT_PASSWORD": "agiloft.password",
            "AGILOFT_KB": "agiloft.kb",
            "AGILOFT_LANGUAGE": "agiloft.language"
        }

        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                self._set_nested_value(config_path, env_value)
                logger.debug(f"Set {config_path} from environment variable {env_var}")

    def _set_nested_value(self, path: str, value: str):
        """Set a nested configuration value using dot notation."""
        keys = path.split('.')
        current = self._config_data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        final_key = keys[-1]
        current[final_key] = self._convert_type(value, current.get(final_key))

    def _convert_type(self, value: str, existing_value: Any) -> Any:
        """Convert string environment variable to appropriate type."""
        if existing_value is None:
            return value

        if isinstance(existing_value, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(existing_value, int):
            return int(value)
        elif isinstance(existing_value, float):
            return float(value)
        else:
            return value

    def get(self, path: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        keys = path.split('.')
        current = self._config_data

        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, path: str, value: Any):
        """Set a configuration value using dot notation."""
        keys = path.split('.')
        current = self._config_data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def validate(self) -> bool:
        """Validate that required configuration is present."""
        required_fields = [
            "agiloft.base_url",
            "agiloft.username",
            "agiloft.password",
            "agiloft.kb"
        ]

        missing_fields = []
        for field in required_fields:
            value = self.get(field)
            if not value:
                missing_fields.append(field)

        if missing_fields:
            logger.error(f"Missing required configuration fields: {missing_fields}")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config_data.copy()

    def __str__(self) -> str:
        """String representation (with sensitive data masked)."""
        safe_config = self.to_dict()
        if 'agiloft' in safe_config and 'password' in safe_config['agiloft']:
            safe_config['agiloft']['password'] = '***masked***'
        return json.dumps(safe_config, indent=2)
