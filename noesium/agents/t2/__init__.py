from typing import TYPE_CHECKING

# Type stubs for lazy imports - fixes linter warnings
if TYPE_CHECKING:
    from .agent import T2Agent
    from .gem_parser import (
        CircularReferenceError,
        GemParser,
        GemParserError,
        GemParserResult,
        TypeMappingError,
        parse_yaml_file,
        parse_yaml_models,
    )


def __getattr__(name: str):
    """Lazy import mechanism - only import modules when they're actually accessed."""
    if name == "T2Agent":
        try:
            from .agent import T2Agent

            return T2Agent
        except ImportError as e:
            raise ImportError(
                f"Failed to import T2Agent: {e}. " "Make sure the required dependencies are installed " "(wizsearch)."
            ) from e

    # Gem parser exports
    gem_parser_attrs = {
        "GemParser": ("noesium.agents.t2.gem_parser", "GemParser"),
        "GemParserError": ("noesium.agents.t2.gem_parser", "GemParserError"),
        "GemParserResult": ("noesium.agents.t2.gem_parser", "GemParserResult"),
        "TypeMappingError": ("noesium.agents.t2.gem_parser", "TypeMappingError"),
        "CircularReferenceError": ("noesium.agents.t2.gem_parser", "CircularReferenceError"),
        "parse_yaml_models": ("noesium.agents.t2.gem_parser", "parse_yaml_models"),
        "parse_yaml_file": ("noesium.agents.t2.gem_parser", "parse_yaml_file"),
    }

    if name in gem_parser_attrs:
        module_path, attr_name = gem_parser_attrs[name]
        try:
            from importlib import import_module

            module = import_module(module_path)
            attr = getattr(module, attr_name)
            globals()[name] = attr
            return attr
        except ImportError as e:
            raise ImportError(f"Failed to import {name} from {module_path}: {e}") from e

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "T2Agent",
    "GemParser",
    "GemParserError",
    "GemParserResult",
    "TypeMappingError",
    "CircularReferenceError",
    "parse_yaml_models",
    "parse_yaml_file",
]
