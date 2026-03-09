"""Configuration Migration System

This module provides a versioned configuration migration system that allows
automatic upgrading of configuration files when the schema changes.

The migration system works by:
1. Reading the version field from the config file
2. Looking up the appropriate migration function for that version
3. Running the migration to transform the config to the next version
4. Repeating until the config is at the latest version

Usage:
    from noesium.core.config_migration import migrate_config

    # Migrate config data to latest version
    migrated_data = migrate_config(config_data, from_version="0.0")
"""

from typing import Any, Dict

from noesium.core.consts import CONFIG_VERSION


def migrate_config(data: Dict[str, Any], from_version: str) -> Dict[str, Any]:
    """Migrate config to latest version.

    This function iteratively applies migration functions to transform
    the configuration data from its current version to the latest version.

    Args:
        data: Configuration data dictionary
        from_version: Current version of the configuration

    Returns:
        Migrated configuration data at the latest version
    """
    current_version = data.get("version", "0.0")

    # Migration registry: maps from_version -> migration_function
    migrations: Dict[str, callable] = {
        "0.0": migrate_0_0_to_1_0,
        # Future migrations will be added here:
        # "1.0": migrate_1_0_to_1_1,
        # "1.1": migrate_1_1_to_2_0,
    }

    # Apply migrations iteratively
    while current_version in migrations:
        data = migrations[current_version](data)
        current_version = data.get("version", CONFIG_VERSION)

    return data


def migrate_0_0_to_1_0(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate from version 0.0 (no version) to 1.0.

    This migration handles the transition from the old flat configuration
    format to the new nested structure.

    Old format (flat):
        {
            "llm_provider": "openai",
            "max_iterations": 25,
            "enabled_toolkits": ["bash", "python_executor"],
            ...
        }

    New format (nested):
        {
            "version": "1.0",
            "llm": {"provider": "openai", ...},
            "agent": {"max_iterations": 25, ...},
            "tools": {"enabled_toolkits": [...], ...},
            ...
        }

    Args:
        data: Configuration data in version 0.0 format

    Returns:
        Configuration data in version 1.0 format
    """
    # Add version field
    data["version"] = "1.0"

    # Restructure LLM config
    if "llm_provider" in data:
        provider = data.pop("llm_provider")
        data.setdefault("llm", {})["provider"] = provider

    # Move model_name to appropriate provider config
    if "model_name" in data:
        model_name = data.pop("model_name")
        provider = data.get("llm", {}).get("provider", "openai")
        data.setdefault("llm", {}).setdefault("providers", {}).setdefault(provider, {})
        data["llm"]["providers"][provider]["chat_model"] = model_name

    # Field mappings: old_key -> (section, new_key)
    field_mappings = {
        # Agent fields
        "mode": ("agent", "mode"),
        "max_iterations": ("agent", "max_iterations"),
        "max_tool_calls_per_step": ("agent", "max_tool_calls_per_step"),
        "reflection_interval": ("agent", "reflection_interval"),
        "planning_model": ("agent", "planning_model"),
        # Tools fields
        "enabled_toolkits": ("tools", "enabled_toolkits"),
        "toolkit_configs": ("tools", "toolkit_configs"),
        "mcp_servers": ("tools", "mcp_servers"),
        "permissions": ("tools", "permissions"),
        # Subagents fields
        "enable_subagents": ("subagents", "enabled"),
        "subagent_max_depth": ("subagents", "max_depth"),
        "agent_subagents": ("subagents", "agent_subagents"),
        "cli_subagents": ("subagents", "cli_subagents"),
        # Memory fields
        "memory_providers": ("memory", "providers"),
        "persist_memory": ("memory", "persist"),
        "session_logging": ("memory", "session_logging"),
        "session_log_dir": ("memory", "session_log_dir"),
        "memu_memory_dir": ("memory", "memu", "memory_dir"),
        "memu_user_id": ("memory", "memu", "user_id"),
        "event_db_path": ("memory", "event_sourced", "db_path"),
        # Tracing fields
        "enable_tracing": ("tracing", "enabled"),
        "tracing_provider": ("tracing", "provider"),
        # Logging fields
        "log_level": ("logging", "level"),
        "log_file": ("logging", "file"),
        "log_rotation": ("logging", "rotation"),
        "log_retention": ("logging", "retention"),
        # Working directory
        "working_directory": ("working_directory", None),
    }

    for old_key, mapping in field_mappings.items():
        if old_key in data:
            value = data.pop(old_key)
            section = mapping[0]
            new_key = mapping[1] if len(mapping) > 1 else None

            if new_key is None:
                # Direct assignment (e.g., working_directory)
                data[section] = value
            elif len(mapping) == 2:
                # Single-level nesting (e.g., agent.max_iterations)
                data.setdefault(section, {})[new_key] = value
            elif len(mapping) == 3:
                # Two-level nesting (e.g., memory.memu.memory_dir)
                intermediate = mapping[1]
                final_key = mapping[2]
                data.setdefault(section, {}).setdefault(intermediate, {})[final_key] = value

    return data


def get_migration_version(data: Dict[str, Any]) -> str:
    """Get the current configuration version.

    Args:
        data: Configuration data dictionary

    Returns:
        Version string, or "0.0" if no version field exists
    """
    return data.get("version", "0.0")


def needs_migration(data: Dict[str, Any]) -> bool:
    """Check if the configuration needs to be migrated.

    Args:
        data: Configuration data dictionary

    Returns:
        True if migration is needed, False otherwise
    """
    current_version = get_migration_version(data)
    return current_version != CONFIG_VERSION


__all__ = [
    "migrate_config",
    "migrate_0_0_to_1_0",
    "get_migration_version",
    "needs_migration",
]
