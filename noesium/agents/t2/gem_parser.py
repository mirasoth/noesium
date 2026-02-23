"""
Gem Parser - Parse Pydantic models from YAML declarations.

This module provides functionality to dynamically create Pydantic models from YAML
configuration files. It supports cross-references between models and handles complex
type relationships using a two-pass parsing approach.
"""

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Collection,
    Container,
    Coroutine,
    Dict,
    FrozenSet,
    Generator,
    Iterable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)
from uuid import UUID

import yaml
from pydantic import BaseModel, Field, create_model

from noesium.core.utils.logging import get_logger

logger = get_logger(__name__)


class GemParserResult(BaseModel):
    """Result structure for gem parser operations.

    This class encapsulates all the information returned by gem parser functions,
    providing a structured and type-safe way to access parsed models and metadata.
    """

    model_config = {"arbitrary_types_allowed": True}

    models: Dict[str, type] = Field(description="Dictionary mapping model names to Pydantic model classes")
    target_model: Optional[type] = Field(default=None, description="Target model class if output_model was specified")
    target_model_name: Optional[str] = Field(
        default=None, description="Target model name if output_model was specified"
    )
    instruction: Optional[str] = Field(default=None, description="Instruction string if specified in YAML")


class GemParserError(Exception):
    """Base exception for gem parser errors."""


class TypeMappingError(GemParserError):
    """Raised when a type cannot be mapped to a Python type."""


class CircularReferenceError(GemParserError):
    """Raised when circular references are detected between models."""


class GemParser:
    """Parser for converting YAML model declarations to Pydantic models."""

    def __init__(self):
        """Initialize the gem parser with default type mappings."""
        self.dynamic_models: Dict[str, type] = {}
        self.type_map = {
            # Basic Python types
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "bytes": bytes,
            "bytearray": bytearray,
            # Special typing types
            "Any": Any,
            # Generic collection types from typing
            "List": List,
            "Dict": Dict,
            "Set": Set,
            "FrozenSet": FrozenSet,
            "Tuple": Tuple,
            "Optional": Optional,
            "Union": Union,
            # Abstract base types from typing (avoiding common model name conflicts)
            "Sequence": Sequence,
            "MutableSequence": MutableSequence,
            "Mapping": Mapping,
            "MutableMapping": MutableMapping,
            "MutableSet": MutableSet,
            "Iterable": Iterable,
            "Iterator": Iterator,
            # Note: 'Container', 'Collection' are omitted to avoid
            # conflicts with common model names. Users can still access them via
            # custom type mappings if needed.
            # Function types
            "Callable": Callable,
            # Async types
            "Awaitable": Awaitable,
            "Coroutine": Coroutine,
            "AsyncIterable": AsyncIterable,
            "AsyncIterator": AsyncIterator,
            "AsyncGenerator": AsyncGenerator,
            "Generator": Generator,
            # Date and time types
            "datetime": datetime,
            "date": date,
            "time": time,
            "timedelta": timedelta,
            "timestamp": int,  # Common representation for timestamps
            # Other useful types
            "Decimal": Decimal,
            "UUID": UUID,
            "Path": Path,
            # Type aliases for convenience
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
        }
        self._dependency_graph: Dict[str, set] = {}

    def add_type_mapping(self, type_name: str, python_type: type) -> None:
        """Add a custom type mapping.

        Args:
            type_name: The string representation of the type in YAML
            python_type: The corresponding Python type
        """
        self.type_map[type_name] = python_type

    def add_typing_types(self, *type_names: str) -> None:
        """Add typing module types to the type map.

        This method allows adding typing types that were excluded from the default
        type_map to avoid conflicts with common model names.

        Args:
            type_names: Names of types from the typing module to add
        """
        typing_types = {
            "Sequence": Sequence,
            "MutableSequence": MutableSequence,
            "Mapping": Mapping,
            "MutableMapping": MutableMapping,
            "MutableSet": MutableSet,
            "Iterable": Iterable,
            "Iterator": Iterator,
            "Collection": Collection,
            "Container": Container,
        }

        for type_name in type_names:
            if type_name in typing_types:
                self.type_map[type_name] = typing_types[type_name]
            else:
                raise ValueError(f"Unknown typing type: {type_name}")

    def parse_from_yaml_string(self, yaml_content: str) -> Dict[str, type]:
        """Parse YAML string and return dynamically created Pydantic models.

        Args:
            yaml_content: YAML string containing model definitions

        Returns:
            Dictionary mapping model names to Pydantic model classes

        Raises:
            GemParserError: If parsing fails
            TypeMappingError: If a type cannot be mapped
            CircularReferenceError: If circular references are detected
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise GemParserError(f"Failed to parse YAML: {e}")

        return self._parse_models(data)

    def parse_from_file(self, file_path: Union[str, Path]) -> Dict[str, type]:
        """Parse YAML file and return dynamically created Pydantic models.

        Args:
            file_path: Path to YAML file containing model definitions

        Returns:
            Dictionary mapping model names to Pydantic model classes
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                yaml_content = f.read()
        except (IOError, OSError) as e:
            raise GemParserError(f"Failed to read file {file_path}: {e}")

        return self.parse_from_yaml_string(yaml_content)

    def _parse_models(self, data: Dict[str, Any]) -> Dict[str, type]:
        """Parse model definitions from loaded YAML data.

        Args:
            data: Parsed YAML data

        Returns:
            Dictionary mapping model names to Pydantic model classes
        """
        # Support both new 'data_models' and legacy 'output_models' keys for backward compatibility
        if "data_models" in data:
            data_models = data["data_models"]
            models_key = "data_models"
        elif "output_models" in data:
            data_models = data["output_models"]
            models_key = "output_models"
        else:
            raise GemParserError("YAML must contain either 'data_models' or 'output_models' key")

        if not isinstance(data_models, list):
            raise GemParserError(f"'{models_key}' must be a list")

        # Check if output_model is specified and validate it
        output_model_name = data.get("output_model")
        if output_model_name:
            model_names = {model_def["name"] for model_def in data_models}
            if output_model_name not in model_names:
                raise GemParserError(f"Specified output_model '{output_model_name}' not found in data_models")

        # Parse instruction field if present
        instruction = data.get("instruction")

        # Reset state for new parsing
        self.dynamic_models.clear()
        self._dependency_graph.clear()
        self._current_data_models = data_models  # Store for type parsing
        self._output_model_name = output_model_name  # Store the target model name
        self._instruction = instruction  # Store the instruction

        # Build dependency graph and detect circular references
        self._build_dependency_graph(data_models)
        self._detect_circular_references()

        # Pass 1: Create placeholder classes to resolve references
        for model_def in data_models:
            model_name = model_def["name"]
            # Create a simple, empty Pydantic model class
            self.dynamic_models[model_name] = type(model_name, (BaseModel,), {})

        # Pass 2: Recreate models with proper fields
        for model_def in data_models:
            self._create_model_with_fields(model_def)

        # Pass 3: Update forward references for all models
        # Create a comprehensive global namespace for forward reference resolution
        global_ns = {}
        global_ns.update(self.type_map)  # Add built-in types
        global_ns.update(self.dynamic_models)  # Add our dynamic models

        # Add common typing imports that might be needed
        import typing

        for attr_name in dir(typing):
            if not attr_name.startswith("_"):
                attr = getattr(typing, attr_name)
                if isinstance(attr, type) or hasattr(attr, "__origin__"):
                    global_ns[attr_name] = attr

        # Rebuild models using dependency-aware resolution with enhanced error handling
        import time

        start_time = time.time()
        max_rebuild_time = 30.0  # 30 second timeout as safety net

        successfully_rebuilt = set()
        failed_models = set(self.dynamic_models.keys())
        rebuild_errors = {}  # Track specific errors for better debugging
        iteration_count = 0

        # Continue until no more progress can be made
        while failed_models:
            # Timeout protection - prevent infinite loops in production
            if time.time() - start_time > max_rebuild_time:
                remaining_models = ", ".join(failed_models)
                logger.error(f"Model rebuild timeout after {max_rebuild_time}s. Remaining: {remaining_models}")
                raise GemParserError(
                    f"Model rebuild timeout after {max_rebuild_time}s. "
                    f"Remaining unresolved models: {remaining_models}. "
                    f"This may indicate circular dependencies or complex forward references."
                )

            iteration_count += 1
            progress_made = False
            models_to_retry = list(failed_models)

            for model_name in models_to_retry:
                model_class = self.dynamic_models[model_name]

                # Check if this model's dependencies have been resolved
                model_dependencies = self._dependency_graph.get(model_name, set())
                unresolved_deps = model_dependencies - successfully_rebuilt

                # If model has unresolved dependencies, skip for now
                if unresolved_deps and model_dependencies:
                    continue

                # Try to rebuild this model
                rebuild_success = False
                last_error = None

                try:
                    # In Pydantic v2, we need to set the models in the module's global namespace
                    # before calling model_rebuild()
                    import sys

                    # Get the module where the model was defined (this gem parser module)
                    model_module = sys.modules[model_class.__module__]

                    # Temporarily add all models to the model's module namespace
                    original_attrs = {}
                    for dep_name, dep_class in self.dynamic_models.items():
                        if hasattr(model_module, dep_name):
                            original_attrs[dep_name] = getattr(model_module, dep_name)
                        setattr(model_module, dep_name, dep_class)

                    try:
                        model_class.model_rebuild()
                        rebuild_success = True
                    finally:
                        # Restore original attributes
                        for dep_name in self.dynamic_models.keys():
                            if dep_name in original_attrs:
                                setattr(model_module, dep_name, original_attrs[dep_name])
                            elif hasattr(model_module, dep_name):
                                delattr(model_module, dep_name)

                except Exception as e:
                    last_error = e
                    # This model still can't be rebuilt - store the error
                    rebuild_errors[model_name] = str(last_error)

                if rebuild_success:
                    successfully_rebuilt.add(model_name)
                    failed_models.discard(model_name)
                    # Clear any previous error for this model
                    rebuild_errors.pop(model_name, None)
                    progress_made = True

            # If no progress was made in this iteration, try to force rebuild remaining models
            if not progress_made and failed_models:
                # Force rebuild any remaining models (they might have circular dependencies)
                remaining_failed = list(failed_models)

                for model_name in remaining_failed:
                    model_class = self.dynamic_models[model_name]
                    last_error = None

                    try:
                        # Use the same approach as above for force rebuild
                        import sys

                        model_module = sys.modules[model_class.__module__]

                        # Temporarily add all models to the model's module namespace
                        original_attrs = {}
                        for dep_name, dep_class in self.dynamic_models.items():
                            if hasattr(model_module, dep_name):
                                original_attrs[dep_name] = getattr(model_module, dep_name)
                            setattr(model_module, dep_name, dep_class)

                        try:
                            model_class.model_rebuild()
                            successfully_rebuilt.add(model_name)
                            failed_models.discard(model_name)
                            rebuild_errors.pop(model_name, None)
                        finally:
                            # Restore original attributes
                            for dep_name in self.dynamic_models.keys():
                                if dep_name in original_attrs:
                                    setattr(model_module, dep_name, original_attrs[dep_name])
                                elif hasattr(model_module, dep_name):
                                    delattr(model_module, dep_name)
                    except Exception as e:
                        last_error = e
                        # Store the final error before giving up on this model
                        rebuild_errors[model_name] = str(last_error)
                        failed_models.discard(model_name)  # Remove to prevent infinite loop

                # After force rebuild attempt, exit the main loop
                break

        # Log completion status
        total_time = time.time() - start_time
        if rebuild_errors:
            logger.warning(
                f"Model rebuild completed with {len(rebuild_errors)} warnings in {total_time:.3f}s "
                f"({len(successfully_rebuilt)} successful, {iteration_count} iterations)"
            )

            # Log detailed errors only at debug level
            import logging

            if logger.isEnabledFor(logging.DEBUG):
                error_details = []
                for model_name, error in rebuild_errors.items():
                    deps = self._dependency_graph.get(model_name, set())
                    error_details.append(f"  - {model_name} (deps: {deps}): {error}")
                logger.debug("Model rebuild errors:\n" + "\n".join(error_details))

        # Final validation: try to create a simple instance of each model to verify they work
        for model_name, model_class in self.dynamic_models.items():
            try:
                # Get the model fields to see if we can create a minimal instance
                model_class.model_fields
                # Just verify the model is properly constructed - don't actually create instance
                # as we don't have valid data
                model_class.model_json_schema()  # This will fail if forward refs aren't resolved
            except Exception:
                # Try one more rebuild if validation fails
                try:
                    import sys

                    model_module = sys.modules[model_class.__module__]

                    # Temporarily add all models to the model's module namespace
                    original_attrs = {}
                    for dep_name, dep_class in self.dynamic_models.items():
                        if hasattr(model_module, dep_name):
                            original_attrs[dep_name] = getattr(model_module, dep_name)
                        setattr(model_module, dep_name, dep_class)

                    try:
                        model_class.model_rebuild()
                    finally:
                        # Restore original attributes
                        for dep_name in self.dynamic_models.keys():
                            if dep_name in original_attrs:
                                setattr(model_module, dep_name, original_attrs[dep_name])
                            elif hasattr(model_module, dep_name):
                                delattr(model_module, dep_name)
                except Exception:
                    pass

        return self.dynamic_models.copy()

    def get_target_model(self) -> Optional[type]:
        """Get the target output model if specified.

        Returns:
            The target Pydantic model class if output_model was specified, None otherwise
        """
        if hasattr(self, "_output_model_name") and self._output_model_name:
            return self.dynamic_models.get(self._output_model_name)
        return None

    def get_target_model_name(self) -> Optional[str]:
        """Get the target output model name if specified.

        Returns:
            The target model name if output_model was specified, None otherwise
        """
        return getattr(self, "_output_model_name", None)

    def get_instruction(self) -> Optional[str]:
        """Get the instruction if specified.

        Returns:
            The instruction string if instruction was specified, None otherwise
        """
        return getattr(self, "_instruction", None)

    def _build_dependency_graph(self, data_models: List[Dict[str, Any]]) -> None:
        """Build a dependency graph to detect circular references.

        Args:
            data_models: List of model definitions
        """
        for model_def in data_models:
            model_name = model_def["name"]
            dependencies = set()

            if "fields" in model_def:
                for field_def in model_def["fields"]:
                    field_type_str = field_def["type"]
                    deps = self._extract_type_dependencies(field_type_str)
                    dependencies.update(deps)

            self._dependency_graph[model_name] = dependencies

    def _extract_type_dependencies(self, type_str: str) -> set:
        """Extract model dependencies from a type string.

        Args:
            type_str: Type string like 'List[Metric]' or 'Optional[Stock]'

        Returns:
            Set of model names that this type depends on
        """
        dependencies = set()

        # Find all custom type references in brackets
        bracket_pattern = r"\[([^\[\]]+)\]"
        matches = re.findall(bracket_pattern, type_str)

        for match in matches:
            # Handle nested types like 'List[Metric]' or 'Dict[str, Stock]'
            parts = [part.strip() for part in match.split(",")]
            for part in parts:
                if part not in self.type_map and part not in ["str", "int", "float", "bool"]:
                    dependencies.add(part)

        # Also check if the type itself is a custom model (not wrapped in brackets)
        if (
            type_str not in self.type_map
            and not any(wrapper in type_str for wrapper in ["List[", "Dict[", "Optional[", "Union["])
            and type_str not in ["str", "int", "float", "bool", "Any"]
        ):
            dependencies.add(type_str)

        return dependencies

    def _detect_circular_references(self) -> None:
        """Detect circular references in the dependency graph.

        Raises:
            CircularReferenceError: If circular references are detected
        """
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self._dependency_graph.get(node, set()):
                if neighbor in self._dependency_graph:  # Only check neighbors that are actual models
                    if neighbor not in visited:
                        if has_cycle(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        return True

            rec_stack.remove(node)
            return False

        for node in self._dependency_graph:
            if node not in visited:
                if has_cycle(node):
                    raise CircularReferenceError(f"Circular reference detected involving model '{node}'")

    def _create_model_with_fields(self, model_def: Dict[str, Any]) -> None:
        """Create a model with proper fields using Pydantic's create_model.

        Args:
            model_def: Model definition dictionary
        """
        model_name = model_def["name"]

        if "fields" not in model_def:
            # Model with no fields - just use the placeholder
            return

        field_definitions = {}

        for field_def in model_def["fields"]:
            field_name = field_def["name"]
            field_type_str = field_def["type"]
            field_desc = field_def.get("desc", "")

            # Parse the field type
            field_type = self._parse_type(field_type_str)

            # Create field definition tuple: (type, Field(...))
            # If field_type is a string (forward reference), use it directly
            field_definitions[field_name] = (field_type, Field(description=field_desc))

        # Create the new model using Pydantic's create_model
        if field_definitions:
            # Set up model config to allow arbitrary types if needed
            from pydantic import ConfigDict

            # Check if any field uses a custom type that might need arbitrary_types_allowed
            def needs_arbitrary_types_check(field_type):
                """Check if a field type needs arbitrary_types_allowed."""
                # If it's a string (forward reference), it doesn't need arbitrary types
                if isinstance(field_type, str):
                    return False

                # If it has an __origin__, it's a generic type - check its args
                if hasattr(field_type, "__origin__"):
                    origin = field_type.__origin__
                    # Standard typing generics don't need arbitrary types
                    if origin in [list, dict, set, frozenset, tuple, type(None)]:
                        return False
                    # Check if the origin itself needs arbitrary types
                    if hasattr(origin, "__module__") and origin.__module__ == "typing":
                        # Most typing module generics are fine
                        return False
                    # Check arguments recursively
                    if hasattr(field_type, "__args__"):
                        return any(needs_arbitrary_types_check(arg) for arg in field_type.__args__)
                    return False

                # Basic Python types don't need arbitrary types (except bytearray)
                if field_type in [str, int, float, bool, bytes, type(None)]:
                    return False
                # bytearray needs arbitrary types in Pydantic
                if field_type == bytearray:
                    return True

                # Standard library types that are usually fine
                if hasattr(field_type, "__module__"):
                    module = field_type.__module__
                    if module in ["builtins", "datetime", "decimal", "uuid", "pathlib", "typing"]:
                        return False

                # Dynamic models don't need arbitrary types
                if field_type in self.dynamic_models.values():
                    return False

                # If we get here, it might need arbitrary types
                return True

            needs_arbitrary_types = any(
                needs_arbitrary_types_check(field_type) for field_type, _ in field_definitions.values()
            )

            if needs_arbitrary_types:
                # Create model with arbitrary types allowed
                model_config = ConfigDict(arbitrary_types_allowed=True)
                new_model = create_model(model_name, __config__=model_config, **field_definitions)
            else:
                new_model = create_model(model_name, **field_definitions)

            self.dynamic_models[model_name] = new_model

    def _parse_type(self, type_str: str) -> Union[type, str]:
        """Parse a type string and return the corresponding Python type or forward reference.

        Args:
            type_str: Type string like 'str', 'List[Metric]', 'Optional[int]'

        Returns:
            Corresponding Python type or forward reference string

        Raises:
            TypeMappingError: If the type cannot be mapped
        """
        type_str = type_str.strip()

        # Handle generic types with square brackets
        if "[" in type_str and type_str.endswith("]"):
            return self._parse_generic_type(type_str)

        # Check if it's a custom model - return as forward reference string
        # This check must come BEFORE type_map to avoid conflicts with typing module names
        if hasattr(self, "_current_data_models") and type_str in [
            model_def["name"] for model_def in self._current_data_models
        ]:
            return type_str  # Return as forward reference string

        # Check if it's a built-in type
        if type_str in self.type_map:
            return self.type_map[type_str]

        raise TypeMappingError(f"Unknown type: {type_str}")

    def _parse_generic_type(self, type_str: str) -> Union[type, str]:
        """Parse a generic type string like 'List[int]', 'Dict[str, int]', etc.

        Args:
            type_str: Generic type string

        Returns:
            Corresponding Python type or forward reference string
        """
        # Extract the base type and arguments
        bracket_start = type_str.index("[")
        base_type_str = type_str[:bracket_start]
        args_str = type_str[bracket_start + 1 : -1]

        # Get the base type
        if base_type_str not in self.type_map:
            raise TypeMappingError(f"Unknown generic type: {base_type_str}")

        base_type = self.type_map[base_type_str]

        # Parse arguments
        args = self._parse_type_arguments(args_str)

        # If any argument is a forward reference, return the whole thing as string
        if any(isinstance(arg, str) for arg in args):
            return type_str

        # Handle different generic types
        try:
            if base_type == List:
                return List[args[0]] if len(args) == 1 else List[Union[tuple(args)]]
            elif base_type == Dict:
                if len(args) != 2:
                    raise TypeMappingError(f"Dict requires exactly 2 type arguments, got {len(args)}")
                return Dict[args[0], args[1]]
            elif base_type == Set:
                return Set[args[0]] if len(args) == 1 else Set[Union[tuple(args)]]
            elif base_type == FrozenSet:
                return FrozenSet[args[0]] if len(args) == 1 else FrozenSet[Union[tuple(args)]]
            elif base_type == Tuple:
                return Tuple[tuple(args)] if args else Tuple[()]
            elif base_type == Optional:
                if len(args) != 1:
                    raise TypeMappingError(f"Optional requires exactly 1 type argument, got {len(args)}")
                return Optional[args[0]]
            elif base_type == Union:
                return Union[tuple(args)] if len(args) > 1 else args[0]
            elif base_type in [Sequence, MutableSequence, Iterable, Collection, Container]:
                return base_type[args[0]] if len(args) == 1 else base_type[Union[tuple(args)]]
            elif base_type in [Mapping, MutableMapping]:
                if len(args) != 2:
                    raise TypeMappingError(f"{base_type_str} requires exactly 2 type arguments, got {len(args)}")
                return base_type[args[0], args[1]]
            elif base_type == MutableSet:
                return MutableSet[args[0]] if len(args) == 1 else MutableSet[Union[tuple(args)]]
            elif base_type == Callable:
                # Callable[[arg_types], return_type] or Callable[..., return_type]
                if len(args) == 2:
                    return Callable[args[0], args[1]]
                else:
                    return Callable[..., args[-1]] if args else Callable
            elif base_type in [Generator, AsyncGenerator]:
                # Generator[yield_type, send_type, return_type]
                if len(args) == 3:
                    return base_type[args[0], args[1], args[2]]
                elif len(args) == 1:
                    return base_type[args[0], None, None]
                else:
                    return base_type
            elif base_type in [Awaitable, Coroutine, AsyncIterable, AsyncIterator]:
                return base_type[args[0]] if len(args) == 1 else base_type
            else:
                # For other generic types, try to apply the arguments
                return base_type[tuple(args)] if args else base_type
        except (TypeError, ValueError) as e:
            raise TypeMappingError(f"Invalid generic type construction for {type_str}: {e}")

    def _parse_type_arguments(self, args_str: str) -> List[Union[type, str]]:
        """Parse type arguments from a string like 'str, int' or 'Dict[str, int], bool'.

        Args:
            args_str: String containing type arguments

        Returns:
            List of parsed types or forward reference strings
        """
        if not args_str.strip():
            return []

        # Special case for empty tuple: Tuple[()]
        if args_str.strip() == "()":
            return []

        # Handle nested brackets by tracking bracket depth
        args = []
        current_arg = ""
        bracket_depth = 0
        paren_depth = 0

        for char in args_str:
            if char == "[":
                bracket_depth += 1
                current_arg += char
            elif char == "]":
                bracket_depth -= 1
                current_arg += char
            elif char == "(":
                paren_depth += 1
                current_arg += char
            elif char == ")":
                paren_depth -= 1
                current_arg += char
            elif char == "," and bracket_depth == 0 and paren_depth == 0:
                # We've reached a top-level comma, so this argument is complete
                arg_str = current_arg.strip()
                if arg_str and arg_str != "()":  # Skip empty parentheses
                    args.append(self._parse_type(arg_str))
                current_arg = ""
            else:
                current_arg += char

        # Add the last argument
        arg_str = current_arg.strip()
        if arg_str and arg_str != "()":  # Skip empty parentheses
            args.append(self._parse_type(arg_str))

        return args


def parse_yaml_models(yaml_content: str, custom_types: Optional[Dict[str, type]] = None) -> GemParserResult:
    """Convenience function to parse YAML models.

    Args:
        yaml_content: YAML string containing model definitions
        custom_types: Optional dictionary of custom type mappings

    Returns:
        GemParserResult containing parsed models and metadata
    """
    parser = GemParser()

    if custom_types:
        for type_name, python_type in custom_types.items():
            parser.add_type_mapping(type_name, python_type)

    models = parser.parse_from_yaml_string(yaml_content)
    target_model = parser.get_target_model()
    target_model_name = parser.get_target_model_name()
    instruction = parser.get_instruction()

    return GemParserResult(
        models=models, target_model=target_model, target_model_name=target_model_name, instruction=instruction
    )


def parse_yaml_file(file_path: Union[str, Path], custom_types: Optional[Dict[str, type]] = None) -> GemParserResult:
    """Convenience function to parse YAML models from file.

    Args:
        file_path: Path to YAML file containing model definitions
        custom_types: Optional dictionary of custom type mappings

    Returns:
        GemParserResult containing parsed models and metadata
    """
    parser = GemParser()

    if custom_types:
        for type_name, python_type in custom_types.items():
            parser.add_type_mapping(type_name, python_type)

    models = parser.parse_from_file(file_path)
    target_model = parser.get_target_model()
    target_model_name = parser.get_target_model_name()
    instruction = parser.get_instruction()

    return GemParserResult(
        models=models, target_model=target_model, target_model_name=target_model_name, instruction=instruction
    )
