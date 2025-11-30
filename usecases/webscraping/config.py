"""
Configuration file parser for web scraping.

This module handles loading and parsing YAML configuration files that define
navigation sequences and data extraction patterns.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .actions import create_action, Action


@dataclass
class ScrapingConfig:
    """Configuration for a web scraping task."""
    name: str
    url: str
    actions: List[Action] = field(default_factory=list)
    output: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    llm_provider: Optional[str] = None
    fallback_provider: Optional[str] = None

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ScrapingConfig":
        """
        Create a ScrapingConfig from a dictionary.

        Args:
            config_dict: Dictionary with configuration data

        Returns:
            ScrapingConfig instance
        """
        # Parse actions
        actions = []
        for action_dict in config_dict.get("actions", []):
            action = create_action(action_dict)
            actions.append(action)

        # Extract other fields
        name = config_dict.get("name", "Unnamed Task")
        url = config_dict["url"]
        output = config_dict.get("output", {})
        metadata = config_dict.get("metadata", {})
        llm_provider = config_dict.get("llm_provider")
        fallback_provider = config_dict.get("fallback_provider")

        return cls(
            name=name,
            url=url,
            actions=actions,
            output=output,
            metadata=metadata,
            llm_provider=llm_provider,
            fallback_provider=fallback_provider
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "url": self.url,
            "actions": [action.to_dict() for action in self.actions],
            "output": self.output,
            "metadata": self.metadata,
            "llm_provider": self.llm_provider,
            "fallback_provider": self.fallback_provider
        }

    def save(self, filepath: Path) -> None:
        """
        Save configuration to YAML file.

        Args:
            filepath: Path to save the configuration
        """
        with open(filepath, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load(cls, filepath: Path) -> "ScrapingConfig":
        """
        Load configuration from YAML file.

        Args:
            filepath: Path to the configuration file

        Returns:
            ScrapingConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        with open(filepath, 'r') as f:
            config_dict = yaml.safe_load(f)

        return cls.from_dict(config_dict)


class ConfigValidator:
    """Validate scraping configurations."""

    @staticmethod
    def validate_config(config: ScrapingConfig) -> tuple[bool, List[str]]:
        """
        Validate a scraping configuration.

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check required fields
        if not config.name:
            errors.append("Configuration must have a name")

        if not config.url:
            errors.append("Configuration must have a URL")

        if not config.actions:
            errors.append("Configuration must have at least one action")

        # Validate URL format
        if config.url and not (config.url.startswith("http://") or config.url.startswith("https://")):
            errors.append(f"Invalid URL format: {config.url}")

        # Validate actions
        for i, action in enumerate(config.actions):
            action_errors = ConfigValidator._validate_action(action, i)
            errors.extend(action_errors)

        # Validate output format
        if config.output:
            output_format = config.output.get("format", "json")
            if output_format not in ["json", "yaml", "csv"]:
                errors.append(f"Invalid output format: {output_format}")

        return len(errors) == 0, errors

    @staticmethod
    def _validate_action(action: Action, index: int) -> List[str]:
        """
        Validate a single action.

        Args:
            action: Action to validate
            index: Index of action in sequence

        Returns:
            List of error messages
        """
        errors = []
        prefix = f"Action {index}"

        # Type-specific validation
        action_dict = action.to_dict()

        if action_dict["type"] == "click":
            if not action_dict.get("selector"):
                errors.append(f"{prefix}: Click action requires selector")

        elif action_dict["type"] == "hover":
            if not action_dict.get("selector"):
                errors.append(f"{prefix}: Hover action requires selector")

        elif action_dict["type"] == "wait":
            if not action_dict.get("selector") and not action_dict.get("duration"):
                errors.append(f"{prefix}: Wait action requires selector or duration")

        elif action_dict["type"] == "extract":
            if not action_dict.get("selectors"):
                errors.append(f"{prefix}: Extract action requires selectors")
            elif not isinstance(action_dict["selectors"], dict):
                errors.append(f"{prefix}: Extract selectors must be a dictionary")

        elif action_dict["type"] == "type":
            if not action_dict.get("selector"):
                errors.append(f"{prefix}: Type action requires selector")
            if not action_dict.get("text"):
                errors.append(f"{prefix}: Type action requires text")

        elif action_dict["type"] == "select":
            if not action_dict.get("selector"):
                errors.append(f"{prefix}: Select action requires selector")
            if not any([
                action_dict.get("value"),
                action_dict.get("label"),
                action_dict.get("index") is not None
            ]):
                errors.append(f"{prefix}: Select action requires value, label, or index")

        elif action_dict["type"] == "screenshot":
            if not action_dict.get("path"):
                errors.append(f"{prefix}: Screenshot action requires path")

        elif action_dict["type"] in ["js", "javascript"]:
            if not action_dict.get("code"):
                errors.append(f"{prefix}: JavaScript action requires code")

        elif action_dict["type"] == "navigate":
            if not action_dict.get("url"):
                errors.append(f"{prefix}: Navigate action requires URL")

        return errors


class ConfigLibrary:
    """Manage a library of scraping configurations."""

    def __init__(self, library_dir: Path):
        """
        Initialize the configuration library.

        Args:
            library_dir: Directory containing configuration files
        """
        self.library_dir = Path(library_dir)
        self.library_dir.mkdir(parents=True, exist_ok=True)

    def list_configs(self) -> List[str]:
        """
        List all available configurations.

        Returns:
            List of configuration names (without .yaml extension)
        """
        configs = []
        for filepath in self.library_dir.glob("*.yaml"):
            configs.append(filepath.stem)
        return sorted(configs)

    def load_config(self, name: str) -> ScrapingConfig:
        """
        Load a configuration by name.

        Args:
            name: Configuration name (without .yaml extension)

        Returns:
            ScrapingConfig instance

        Raises:
            FileNotFoundError: If configuration doesn't exist
        """
        filepath = self.library_dir / f"{name}.yaml"
        return ScrapingConfig.load(filepath)

    def save_config(self, config: ScrapingConfig, name: Optional[str] = None) -> Path:
        """
        Save a configuration to the library.

        Args:
            config: Configuration to save
            name: Optional name (uses config.name if not provided)

        Returns:
            Path where configuration was saved
        """
        config_name = name or config.name
        # Sanitize filename
        config_name = config_name.replace(" ", "_").lower()
        filepath = self.library_dir / f"{config_name}.yaml"

        config.save(filepath)
        return filepath

    def delete_config(self, name: str) -> bool:
        """
        Delete a configuration.

        Args:
            name: Configuration name

        Returns:
            True if deleted, False if not found
        """
        filepath = self.library_dir / f"{name}.yaml"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def get_config_info(self, name: str) -> Dict[str, Any]:
        """
        Get information about a configuration without loading it.

        Args:
            name: Configuration name

        Returns:
            Dictionary with configuration metadata
        """
        filepath = self.library_dir / f"{name}.yaml"
        if not filepath.exists():
            raise FileNotFoundError(f"Configuration not found: {name}")

        config = self.load_config(name)
        return {
            "name": config.name,
            "url": config.url,
            "num_actions": len(config.actions),
            "output_format": config.output.get("format", "json"),
            "llm_provider": config.llm_provider,
            "fallback_provider": config.fallback_provider
        }
