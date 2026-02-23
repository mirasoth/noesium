"""
Unit tests for the noesium.agents.t2.gem_parser module.
"""

import os
import tempfile
from datetime import datetime

import pytest
from pydantic import BaseModel

from noesium.agents.t2 import (
    CircularReferenceError,
    GemParser,
    GemParserError,
    GemParserResult,
    TypeMappingError,
    parse_yaml_file,
    parse_yaml_models,
)


class TestGemParser:
    """Test cases for the GemParser class."""

    def test_basic_model_parsing(self):
        """Test parsing a simple model with basic types."""
        yaml_content = """
task: StructuredExtraction
metadata:
  name: basic test
data_models:
  - name: SimpleModel
    fields:
    - name: text_field
      type: str
      desc: A text field
    - name: number_field
      type: int
      desc: A number field
    - name: flag_field
      type: bool
      desc: A boolean field
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        assert "SimpleModel" in models
        SimpleModel = models["SimpleModel"]

        # Test model creation
        instance = SimpleModel(text_field="test", number_field=42, flag_field=True)
        assert instance.text_field == "test"
        assert instance.number_field == 42
        assert instance.flag_field is True

        # Test field descriptions
        fields = SimpleModel.model_fields
        assert fields["text_field"].description == "A text field"
        assert fields["number_field"].description == "A number field"
        assert fields["flag_field"].description == "A boolean field"

    def test_cross_reference_models(self):
        """Test parsing models with cross-references (the main example)."""
        yaml_content = """
task: StructuredExtraction
metadata:
  name: hello world
data_models:
  - name: Metric
    fields:
    - name: metric_key
      type: str
      desc: metric name string
    - name: metric_time
      type: Any
      desc: collection timestamp of metric
  - name: Stock
    fields:
    - name: metrics
      type: List[Metric]
      desc: all metrics of stock
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        assert "Metric" in models
        assert "Stock" in models

        Metric = models["Metric"]
        Stock = models["Stock"]

        # Test creating instances
        metric1 = Metric(metric_key="price", metric_time=1678886400)
        metric2 = Metric(metric_key="volume", metric_time=1678886500)

        stock = Stock(metrics=[metric1, metric2])

        assert len(stock.metrics) == 2
        assert stock.metrics[0].metric_key == "price"
        assert stock.metrics[1].metric_key == "volume"

        # Test validation
        with pytest.raises(Exception):  # Should fail validation
            Stock(metrics=[{"invalid": "data"}])

    def test_complex_types(self):
        """Test parsing models with complex type annotations."""
        yaml_content = """
task: StructuredExtraction
data_models:
  - name: ComplexModel
    fields:
    - name: optional_field
      type: Optional[str]
      desc: An optional string field
    - name: dict_field
      type: Dict[str, int]
      desc: A dictionary field
    - name: union_field
      type: Union[str, int]
      desc: A union field
    - name: datetime_field
      type: datetime
      desc: A datetime field
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        ComplexModel = models["ComplexModel"]

        # Test with valid data
        instance = ComplexModel(
            optional_field="test",
            dict_field={"key1": 1, "key2": 2},
            union_field="string_value",
            datetime_field=datetime.now(),
        )

        assert instance.optional_field == "test"
        assert instance.dict_field == {"key1": 1, "key2": 2}
        assert instance.union_field == "string_value"
        assert isinstance(instance.datetime_field, datetime)

        # Test with None optional field
        instance2 = ComplexModel(optional_field=None, dict_field={}, union_field=42, datetime_field=datetime.now())

        assert instance2.optional_field is None
        assert instance2.union_field == 42

    def test_custom_type_mapping(self):
        """Test adding custom type mappings."""

        class CustomType:
            def __init__(self, value):
                self.value = value

        yaml_content = """
data_models:
  - name: CustomModel
    fields:
    - name: custom_field
      type: custom_type
      desc: A custom type field
"""

        parser = GemParser()
        parser.add_type_mapping("custom_type", CustomType)

        models = parser.parse_from_yaml_string(yaml_content)
        CustomModel = models["CustomModel"]

        # The field should accept the custom type
        CustomModel.model_fields
        # Note: The actual type checking depends on Pydantic's behavior with custom types

    def test_circular_reference_detection(self):
        """Test detection of circular references between models."""
        yaml_content = """
data_models:
  - name: ModelA
    fields:
    - name: b_ref
      type: ModelB
      desc: Reference to ModelB
  - name: ModelB
    fields:
    - name: a_ref
      type: ModelA
      desc: Reference to ModelA
"""

        parser = GemParser()

        with pytest.raises(CircularReferenceError):
            parser.parse_from_yaml_string(yaml_content)

    def test_missing_data_models(self):
        """Test error handling when data_models is missing."""
        yaml_content = """
task: StructuredExtraction
metadata:
  name: invalid test
"""

        parser = GemParser()

        with pytest.raises(GemParserError, match="YAML must contain either 'data_models' or 'output_models' key"):
            parser.parse_from_yaml_string(yaml_content)

    def test_invalid_yaml(self):
        """Test error handling for invalid YAML."""
        invalid_yaml = """
task: StructuredExtraction
invalid: yaml: content:
  - broken
"""

        parser = GemParser()

        with pytest.raises(GemParserError, match="Failed to parse YAML"):
            parser.parse_from_yaml_string(invalid_yaml)

    def test_unknown_type(self):
        """Test error handling for unknown types."""
        yaml_content = """
data_models:
  - name: BadModel
    fields:
    - name: bad_field
      type: UnknownType
      desc: A field with unknown type
"""

        parser = GemParser()

        with pytest.raises(TypeMappingError, match="Unknown type: UnknownType"):
            parser.parse_from_yaml_string(yaml_content)

    def test_nested_list_types(self):
        """Test parsing nested list types."""
        yaml_content = """
data_models:
  - name: Item
    fields:
    - name: name
      type: str
      desc: Item name
  - name: ItemContainer
    fields:
    - name: items
      type: List[Item]
      desc: List of items
  - name: SuperContainer
    fields:
    - name: containers
      type: List[ItemContainer]
      desc: List of containers
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        Item = models["Item"]
        ItemContainer = models["ItemContainer"]
        SuperContainer = models["SuperContainer"]

        # Test nested structure
        item1 = Item(name="item1")
        item2 = Item(name="item2")
        container = ItemContainer(items=[item1, item2])
        super_container = SuperContainer(containers=[container])

        assert len(super_container.containers) == 1
        assert len(super_container.containers[0].items) == 2
        assert super_container.containers[0].items[0].name == "item1"

    def test_file_parsing(self):
        """Test parsing from file."""
        yaml_content = """
data_models:
  - name: FileModel
    fields:
    - name: field1
      type: str
      desc: First field
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            parser = GemParser()
            models = parser.parse_from_file(temp_path)

            assert "FileModel" in models
            FileModel = models["FileModel"]

            instance = FileModel(field1="test")
            assert instance.field1 == "test"
        finally:
            os.unlink(temp_path)

    def test_file_not_found(self):
        """Test error handling when file doesn't exist."""
        parser = GemParser()

        with pytest.raises(GemParserError, match="Failed to read file"):
            parser.parse_from_file("/nonexistent/path/file.yaml")

    def test_empty_fields(self):
        """Test model with no fields."""
        yaml_content = """
data_models:
  - name: EmptyModel
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        EmptyModel = models["EmptyModel"]
        instance = EmptyModel()

        # Should work fine with no fields
        assert isinstance(instance, BaseModel)

    def test_model_order_independence(self):
        """Test that model definition order doesn't matter."""
        yaml_content = """
data_models:
  - name: Stock
    fields:
    - name: metrics
      type: List[Metric]
      desc: all metrics of stock
  - name: Metric
    fields:
    - name: metric_key
      type: str
      desc: metric name string
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        # Should work even though Stock is defined before Metric
        Metric = models["Metric"]
        Stock = models["Stock"]

        metric = Metric(metric_key="test")
        stock = Stock(metrics=[metric])

        assert stock.metrics[0].metric_key == "test"


class TestConvenienceFunctions:
    """Test the convenience functions."""

    def test_parse_yaml_models(self):
        """Test the parse_yaml_models convenience function."""
        yaml_content = """
data_models:
  - name: TestModel
    fields:
    - name: field1
      type: str
      desc: Test field
"""

        result = parse_yaml_models(yaml_content)
        assert isinstance(result, GemParserResult)
        assert "TestModel" in result.models

        TestModel = result.models["TestModel"]
        instance = TestModel(field1="test")
        assert instance.field1 == "test"

    def test_parse_yaml_models_with_custom_types(self):
        """Test parse_yaml_models with custom type mappings."""

        class MyCustomType:
            pass

        yaml_content = """
data_models:
  - name: CustomModel
    fields:
    - name: custom_field
      type: my_custom
      desc: Custom field
"""

        custom_types = {"my_custom": MyCustomType}
        result = parse_yaml_models(yaml_content, custom_types=custom_types)

        assert isinstance(result, GemParserResult)
        assert "CustomModel" in result.models

    def test_parse_yaml_file_function(self):
        """Test the parse_yaml_file convenience function."""
        yaml_content = """
data_models:
  - name: FileTestModel
    fields:
    - name: field1
      type: str
      desc: Test field
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = parse_yaml_file(temp_path)
            assert isinstance(result, GemParserResult)
            assert "FileTestModel" in result.models

            FileTestModel = result.models["FileTestModel"]
            instance = FileTestModel(field1="test")
            assert instance.field1 == "test"
        finally:
            os.unlink(temp_path)


class TestTypingLibrarySupport:
    """Test comprehensive typing library support."""

    def test_basic_collection_types(self):
        """Test basic collection types from typing library."""
        yaml_content = """
data_models:
  - name: CollectionModel
    fields:
    - name: list_field
      type: List[str]
      desc: List of strings
    - name: dict_field
      type: Dict[str, int]
      desc: Dictionary mapping
    - name: set_field
      type: Set[int]
      desc: Set of integers
    - name: frozenset_field
      type: FrozenSet[str]
      desc: Frozen set of strings
    - name: tuple_field
      type: Tuple[str, int, bool]
      desc: Tuple with mixed types
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        CollectionModel = models["CollectionModel"]

        # Test creation with valid data
        instance = CollectionModel(
            list_field=["a", "b", "c"],
            dict_field={"x": 1, "y": 2},
            set_field={1, 2, 3},
            frozenset_field=frozenset(["p", "q"]),
            tuple_field=("hello", 42, True),
        )

        assert instance.list_field == ["a", "b", "c"]
        assert instance.dict_field == {"x": 1, "y": 2}
        assert instance.set_field == {1, 2, 3}
        assert instance.frozenset_field == frozenset(["p", "q"])
        assert instance.tuple_field == ("hello", 42, True)

    def test_abstract_base_types(self):
        """Test abstract base types from typing library."""
        yaml_content = """
data_models:
  - name: AbstractModel
    fields:
    - name: sequence_field
      type: Sequence[int]
      desc: Sequence of integers
    - name: mapping_field
      type: Mapping[str, float]
      desc: Mapping of strings to floats
    - name: mutable_sequence_field
      type: MutableSequence[str]
      desc: Mutable sequence of strings
    - name: mutable_mapping_field
      type: MutableMapping[str, bool]
      desc: Mutable mapping
    - name: iterable_field
      type: Iterable[str]
      desc: Iterable of strings
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        AbstractModel = models["AbstractModel"]

        # Test creation - these should accept compatible concrete types
        instance = AbstractModel(
            sequence_field=[1, 2, 3],  # List is a Sequence
            mapping_field={"a": 1.0, "b": 2.0},  # Dict is a Mapping
            mutable_sequence_field=["x", "y"],  # List is a MutableSequence
            mutable_mapping_field={"flag": True},  # Dict is a MutableMapping
            iterable_field=["p", "q", "r"],  # List is an Iterable
        )

        assert instance.sequence_field == [1, 2, 3]
        assert instance.mapping_field == {"a": 1.0, "b": 2.0}
        assert instance.mutable_sequence_field == ["x", "y"]
        assert instance.mutable_mapping_field == {"flag": True}
        # Iterable might be converted to an iterator by Pydantic, so check if it contains the expected values
        iterable_values = (
            list(instance.iterable_field) if hasattr(instance.iterable_field, "__iter__") else instance.iterable_field
        )
        assert iterable_values == ["p", "q", "r"]

    def test_datetime_types(self):
        """Test datetime-related types."""
        yaml_content = """
data_models:
  - name: DateTimeModel
    fields:
    - name: datetime_field
      type: datetime
      desc: Datetime field
    - name: date_field
      type: date
      desc: Date field
    - name: time_field
      type: time
      desc: Time field
    - name: timedelta_field
      type: timedelta
      desc: Time delta field
"""

        from datetime import date, datetime, time, timedelta

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        DateTimeModel = models["DateTimeModel"]

        instance = DateTimeModel(
            datetime_field=datetime(2023, 1, 1, 12, 0, 0),
            date_field=date(2023, 1, 1),
            time_field=time(12, 0, 0),
            timedelta_field=timedelta(days=1, hours=2),
        )

        assert isinstance(instance.datetime_field, datetime)
        assert isinstance(instance.date_field, date)
        assert isinstance(instance.time_field, time)
        assert isinstance(instance.timedelta_field, timedelta)

    def test_other_useful_types(self):
        """Test other useful types like Decimal, UUID, Path."""
        yaml_content = """
data_models:
  - name: UtilityModel
    fields:
    - name: decimal_field
      type: Decimal
      desc: Decimal field
    - name: uuid_field
      type: UUID
      desc: UUID field
    - name: path_field
      type: Path
      desc: Path field
"""

        from decimal import Decimal
        from pathlib import Path
        from uuid import UUID, uuid4

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        UtilityModel = models["UtilityModel"]

        test_uuid = uuid4()
        instance = UtilityModel(decimal_field=Decimal("123.45"), uuid_field=test_uuid, path_field=Path("/tmp/test"))

        assert isinstance(instance.decimal_field, Decimal)
        assert instance.decimal_field == Decimal("123.45")
        assert isinstance(instance.uuid_field, UUID)
        assert instance.uuid_field == test_uuid
        assert isinstance(instance.path_field, Path)
        assert instance.path_field == Path("/tmp/test")

    def test_type_aliases(self):
        """Test type aliases for convenience."""
        yaml_content = """
data_models:
  - name: AliasModel
    fields:
    - name: string_field
      type: string
      desc: String field using alias
    - name: integer_field
      type: integer
      desc: Integer field using alias
    - name: number_field
      type: number
      desc: Number field using alias
    - name: boolean_field
      type: boolean
      desc: Boolean field using alias
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        AliasModel = models["AliasModel"]

        instance = AliasModel(string_field="test", integer_field=42, number_field=3.14, boolean_field=True)

        assert instance.string_field == "test"
        assert instance.integer_field == 42
        assert instance.number_field == 3.14
        assert instance.boolean_field is True

    def test_nested_generic_types(self):
        """Test nested generic types."""
        yaml_content = """
data_models:
  - name: NestedModel
    fields:
    - name: list_of_dicts
      type: List[Dict[str, int]]
      desc: List of dictionaries
    - name: dict_of_lists
      type: Dict[str, List[float]]
      desc: Dictionary of lists
    - name: optional_list
      type: Optional[List[str]]
      desc: Optional list
    - name: union_types
      type: Union[str, int, List[bool]]
      desc: Union of multiple types
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        NestedModel = models["NestedModel"]

        instance = NestedModel(
            list_of_dicts=[{"a": 1}, {"b": 2}],
            dict_of_lists={"x": [1.1, 2.2], "y": [3.3]},
            optional_list=["p", "q"],
            union_types="string_value",
        )

        assert instance.list_of_dicts == [{"a": 1}, {"b": 2}]
        assert instance.dict_of_lists == {"x": [1.1, 2.2], "y": [3.3]}
        assert instance.optional_list == ["p", "q"]
        assert instance.union_types == "string_value"

        # Test with different union type
        instance2 = NestedModel(list_of_dicts=[], dict_of_lists={}, optional_list=None, union_types=[True, False])

        assert instance2.optional_list is None
        assert instance2.union_types == [True, False]

    def test_bytes_and_bytearray(self):
        """Test bytes and bytearray types."""
        yaml_content = """
data_models:
  - name: BytesModel
    fields:
    - name: bytes_field
      type: bytes
      desc: Bytes field
    - name: bytearray_field
      type: bytearray
      desc: Bytearray field
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        BytesModel = models["BytesModel"]

        instance = BytesModel(bytes_field=b"hello", bytearray_field=bytearray(b"world"))

        assert instance.bytes_field == b"hello"
        assert instance.bytearray_field == bytearray(b"world")

    def test_complex_tuple_types(self):
        """Test various tuple type configurations."""
        yaml_content = """
data_models:
  - name: TupleModel
    fields:
    - name: empty_tuple
      type: Tuple[()]
      desc: Empty tuple
    - name: single_tuple
      type: Tuple[int]
      desc: Single element tuple type
    - name: mixed_tuple
      type: Tuple[str, int, bool, float]
      desc: Mixed type tuple
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        TupleModel = models["TupleModel"]

        instance = TupleModel(empty_tuple=(), single_tuple=(42,), mixed_tuple=("test", 123, True, 3.14))

        assert instance.empty_tuple == ()
        assert instance.single_tuple == (42,)
        assert instance.mixed_tuple == ("test", 123, True, 3.14)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_complex_nested_types(self):
        """Test very complex nested type structures."""
        yaml_content = """
data_models:
  - name: BaseItem
    fields:
    - name: id
      type: str
      desc: Item ID
  - name: ComplexModel
    fields:
    - name: nested_dict
      type: Dict[str, List[BaseItem]]
      desc: Complex nested structure
    - name: optional_list
      type: Optional[List[str]]
      desc: Optional list of strings
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        BaseItem = models["BaseItem"]
        ComplexModel = models["ComplexModel"]

        item = BaseItem(id="test123")
        complex_instance = ComplexModel(nested_dict={"key1": [item]}, optional_list=["a", "b", "c"])

        assert complex_instance.nested_dict["key1"][0].id == "test123"
        assert complex_instance.optional_list == ["a", "b", "c"]

    def test_self_reference_error(self):
        """Test that self-references are detected as circular."""
        yaml_content = """
data_models:
  - name: SelfRef
    fields:
    - name: self_field
      type: SelfRef
      desc: Self reference
"""

        parser = GemParser()

        with pytest.raises(CircularReferenceError):
            parser.parse_from_yaml_string(yaml_content)

    def test_invalid_data_models_type(self):
        """Test error when data_models is not a list."""
        yaml_content = """
data_models: "not a list"
"""

        parser = GemParser()

        with pytest.raises(GemParserError, match="'data_models' must be a list"):
            parser.parse_from_yaml_string(yaml_content)

    def test_missing_field_name(self):
        """Test handling of missing field names."""
        yaml_content = """
data_models:
  - name: BadFieldModel
    fields:
    - type: str
      desc: Missing name field
"""

        parser = GemParser()

        # This should raise an error when trying to access the missing 'name' key
        with pytest.raises(KeyError):
            parser.parse_from_yaml_string(yaml_content)

    def test_missing_field_type(self):
        """Test handling of missing field types."""
        yaml_content = """
data_models:
  - name: BadFieldModel
    fields:
    - name: bad_field
      desc: Missing type field
"""

        parser = GemParser()

        # This should raise an error when trying to access the missing 'type' key
        with pytest.raises(KeyError):
            parser.parse_from_yaml_string(yaml_content)

    def test_type_dependency_extraction(self):
        """Test the type dependency extraction logic."""
        parser = GemParser()

        # Test various type patterns
        assert parser._extract_type_dependencies("str") == set()
        assert parser._extract_type_dependencies("List[CustomType]") == {"CustomType"}
        assert parser._extract_type_dependencies("Dict[str, CustomType]") == {"CustomType"}
        assert parser._extract_type_dependencies("Optional[CustomType]") == {"CustomType"}
        assert parser._extract_type_dependencies("Union[str, CustomType]") == {"CustomType"}
        assert parser._extract_type_dependencies("List[Dict[str, CustomType]]") == {"CustomType"}

    def test_multiple_dependencies(self):
        """Test models with multiple dependencies."""
        yaml_content = """
data_models:
  - name: ModelA
    fields:
    - name: field_a
      type: str
      desc: String field
  - name: ModelB
    fields:
    - name: field_b
      type: int
      desc: Int field
  - name: ModelC
    fields:
    - name: a_ref
      type: ModelA
      desc: Reference to A
    - name: b_ref
      type: ModelB
      desc: Reference to B
    - name: mixed_list
      type: List[Union[ModelA, ModelB]]
      desc: Mixed list
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        ModelA = models["ModelA"]
        ModelB = models["ModelB"]
        ModelC = models["ModelC"]

        # Test creating instances
        a = ModelA(field_a="test")
        b = ModelB(field_b=42)
        c = ModelC(a_ref=a, b_ref=b, mixed_list=[a, b])

        assert c.a_ref.field_a == "test"
        assert c.b_ref.field_b == 42
        assert len(c.mixed_list) == 2


class TestOutputModelFeature:
    """Test the new output_model feature."""

    def test_output_model_basic(self):
        """Test basic output_model functionality."""
        yaml_content = """
data_models:
  - name: ModelA
    fields:
    - name: field_a
      type: str
      desc: String field
  - name: ModelB
    fields:
    - name: field_b
      type: int
      desc: Int field
output_model: ModelA
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        # Should have both models
        assert "ModelA" in models
        assert "ModelB" in models

        # Should have target model set
        target_model = parser.get_target_model()
        target_model_name = parser.get_target_model_name()

        assert target_model is not None
        assert target_model_name == "ModelA"
        assert target_model == models["ModelA"]

    def test_output_model_invalid(self):
        """Test error when output_model references non-existent model."""
        yaml_content = """
data_models:
  - name: ModelA
    fields:
    - name: field_a
      type: str
      desc: String field
output_model: NonExistentModel
"""

        parser = GemParser()

        with pytest.raises(GemParserError, match="Specified output_model 'NonExistentModel' not found in data_models"):
            parser.parse_from_yaml_string(yaml_content)

    def test_no_output_model(self):
        """Test behavior when no output_model is specified."""
        yaml_content = """
data_models:
  - name: ModelA
    fields:
    - name: field_a
      type: str
      desc: String field
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        # Should have the model
        assert "ModelA" in models

        # Should have no target model
        target_model = parser.get_target_model()
        target_model_name = parser.get_target_model_name()

        assert target_model is None
        assert target_model_name is None

    def test_convenience_functions_with_output_model(self):
        """Test convenience functions return GemParserResult with target_model when output_model is specified."""
        yaml_content = """
data_models:
  - name: TestModel
    fields:
    - name: field1
      type: str
      desc: Test field
output_model: TestModel
"""

        result = parse_yaml_models(yaml_content)

        # Should return GemParserResult with target_model when output_model is specified
        assert isinstance(result, GemParserResult)
        assert "TestModel" in result.models
        assert result.target_model == result.models["TestModel"]
        assert result.target_model_name == "TestModel"
        assert result.instruction is None

    def test_convenience_functions_without_output_model(self):
        """Test convenience functions return GemParserResult without target_model when no output_model is specified."""
        yaml_content = """
data_models:
  - name: TestModel
    fields:
    - name: field1
      type: str
      desc: Test field
"""

        result = parse_yaml_models(yaml_content)

        # Should return GemParserResult without target_model when no output_model is specified
        assert isinstance(result, GemParserResult)
        assert "TestModel" in result.models
        assert result.target_model is None
        assert result.target_model_name is None
        assert result.instruction is None

    def test_backward_compatibility(self):
        """Test backward compatibility with output_models key."""
        yaml_content = """
output_models:
  - name: LegacyModel
    fields:
    - name: field1
      type: str
      desc: Test field
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        assert "LegacyModel" in models

        # Should work with no output_model specified
        target_model = parser.get_target_model()
        assert target_model is None


class TestInstructionFeature:
    """Test the new instruction field feature."""

    def test_instruction_basic(self):
        """Test basic instruction field functionality."""
        yaml_content = """
data_models:
  - name: TestModel
    fields:
    - name: field_a
      type: str
      desc: String field
instruction: Process the data according to requirements
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        # Should have the model
        assert "TestModel" in models

        # Should have instruction set
        instruction = parser.get_instruction()
        assert instruction == "Process the data according to requirements"

    def test_instruction_with_output_model(self):
        """Test instruction combined with output_model functionality."""
        yaml_content = """
data_models:
  - name: ModelA
    fields:
    - name: field_a
      type: str
      desc: String field
  - name: ModelB
    fields:
    - name: field_b
      type: int
      desc: Int field
output_model: ModelA
instruction: Extract data using ModelA schema
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        # Should have both models
        assert "ModelA" in models
        assert "ModelB" in models

        # Should have target model and instruction set
        target_model = parser.get_target_model()
        target_model_name = parser.get_target_model_name()
        instruction = parser.get_instruction()

        assert target_model is not None
        assert target_model_name == "ModelA"
        assert target_model == models["ModelA"]
        assert instruction == "Extract data using ModelA schema"

    def test_no_instruction(self):
        """Test behavior when no instruction is specified."""
        yaml_content = """
data_models:
  - name: ModelA
    fields:
    - name: field_a
      type: str
      desc: String field
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        # Should have the model
        assert "ModelA" in models

        # Should have no instruction
        instruction = parser.get_instruction()
        assert instruction is None

    def test_convenience_functions_with_instruction(self):
        """Test convenience functions with instruction field."""
        yaml_content = """
data_models:
  - name: TestModel
    fields:
    - name: field1
      type: str
      desc: Test field
output_model: TestModel
instruction: Test instruction for extraction
"""

        result = parse_yaml_models(yaml_content)

        # Should return GemParserResult when both output_model and instruction are specified
        assert isinstance(result, GemParserResult)
        assert "TestModel" in result.models
        assert result.target_model == result.models["TestModel"]
        assert result.target_model_name == "TestModel"
        assert result.instruction == "Test instruction for extraction"

    def test_convenience_functions_output_model_no_instruction(self):
        """Test convenience functions with output_model but no instruction."""
        yaml_content = """
data_models:
  - name: TestModel
    fields:
    - name: field1
      type: str
      desc: Test field
output_model: TestModel
"""

        result = parse_yaml_models(yaml_content)

        # Should return GemParserResult when only output_model is specified
        assert isinstance(result, GemParserResult)
        assert "TestModel" in result.models
        assert result.target_model == result.models["TestModel"]
        assert result.target_model_name == "TestModel"
        assert result.instruction is None

    def test_parse_yaml_file_with_instruction(self):
        """Test parse_yaml_file function with instruction field."""
        yaml_content = """
data_models:
  - name: FileTestModel
    fields:
    - name: field1
      type: str
      desc: Test field
output_model: FileTestModel
instruction: File-based instruction test
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = parse_yaml_file(temp_path)

            # Should return GemParserResult when both output_model and instruction are specified
            assert isinstance(result, GemParserResult)
            assert "FileTestModel" in result.models
            assert result.target_model == result.models["FileTestModel"]
            assert result.target_model_name == "FileTestModel"
            assert result.instruction == "File-based instruction test"
        finally:
            os.unlink(temp_path)

    def test_snowman_balance_example(self):
        """Test parsing the actual snowman_balance.yml example."""
        yaml_content = """
task: StructuredExtraction
metadata:
  name: 公司财报关键指标解析
data_models:
  - name: StockMetric
    fields:
    - name: metric_name
      type: str
      desc: 指标名称，如营业收入、营业收入同比增长、净利润
    - name: report_time
      type: str
      desc: 报告时间，如2024中报、2024三季报
    - name: value
      type: str
      desc: 指标值，如100亿
    - name: yoy_growth
      type: str
      desc: 同比增长，如-10%
  - name: StockKeyMetricsAll
    fields:
    - name: stock_name
      type: str
      desc: 股票名称，如雪人股份
    - name: stock_code
      type: str
      desc: 股票代码，如002639
    - name: key_measures
      type: List[StockMetric]
      desc: 关键指标
    - name: per_stock_measures
      type: List[StockMetric]
      desc: 每股指标
    - name: profitability
      type: List[StockMetric]
      desc: 盈利能力指标
    - name: financial_risks
      type: List[StockMetric]
      desc: 财务风险指标
    - name: opertional_capacity
      type: List[StockMetric]
      desc: 运营能力指标
instruction: 页面加载完成后，选择【同比】按钮，解析【关键指标】、【每股指标】、【盈利能力】、【财务风险】、【运营能力】五类指标，并格式化输出到指定数据结构
output_model: StockKeyMetricsAll
"""

        parser = GemParser()
        models = parser.parse_from_yaml_string(yaml_content)

        # Should have both models
        assert "StockMetric" in models
        assert "StockKeyMetricsAll" in models

        # Should have target model and instruction set
        target_model = parser.get_target_model()
        target_model_name = parser.get_target_model_name()
        instruction = parser.get_instruction()

        assert target_model is not None
        assert target_model_name == "StockKeyMetricsAll"
        assert target_model == models["StockKeyMetricsAll"]
        assert (
            instruction
            == "页面加载完成后，选择【同比】按钮，解析【关键指标】、【每股指标】、【盈利能力】、【财务风险】、【运营能力】五类指标，并格式化输出到指定数据结构"
        )

        # Test model creation
        StockMetric = models["StockMetric"]
        StockKeyMetricsAll = models["StockKeyMetricsAll"]

        # Create a test instance
        metric = StockMetric(metric_name="营业收入", report_time="2024中报", value="100亿", yoy_growth="10%")

        stock_metrics = StockKeyMetricsAll(
            stock_name="雪人股份",
            stock_code="002639",
            key_measures=[metric],
            per_stock_measures=[],
            profitability=[],
            financial_risks=[],
            opertional_capacity=[],
        )

        assert stock_metrics.stock_name == "雪人股份"
        assert stock_metrics.stock_code == "002639"
        assert len(stock_metrics.key_measures) == 1
        assert stock_metrics.key_measures[0].metric_name == "营业收入"


class TestInfiniteLoopPrevention:
    """Test cases for preventing infinite loops in dependency resolution."""

    def test_undefined_dependency_no_infinite_loop(self):
        """Test that undefined dependencies don't cause infinite loops."""
        yaml_content = """
data_models:
  - name: ProblematicModel
    fields:
    - name: undefined_ref
      type: UndefinedModel
      desc: Reference to undefined model
  - name: SimpleModel
    fields:
    - name: value
      type: str
      desc: Simple field
"""

        parser = GemParser()

        # This should raise an exception quickly, not hang in infinite loop
        import time

        start_time = time.time()

        with pytest.raises(TypeMappingError, match="Unknown type: UndefinedModel"):
            parser.parse_from_yaml_string(yaml_content)

        end_time = time.time()

        # Should complete very quickly (less than 1 second)
        assert (end_time - start_time) < 1.0, "Should fail quickly without infinite loop"

    def test_complex_dependency_chain_no_infinite_loop(self):
        """Test that complex but valid dependency chains don't cause infinite loops."""
        yaml_content = """
data_models:
  - name: ModelD
    fields:
    - name: value
      type: str
      desc: Final value
  - name: ModelC
    fields:
    - name: d_ref
      type: ModelD
      desc: Reference to D
  - name: ModelB
    fields:
    - name: c_ref
      type: ModelC
      desc: Reference to C
  - name: ModelA
    fields:
    - name: b_ref
      type: ModelB
      desc: Reference to B
"""

        parser = GemParser()

        import time

        start_time = time.time()

        # This should complete successfully and quickly
        models = parser.parse_from_yaml_string(yaml_content)

        end_time = time.time()

        # Should complete quickly (less than 1 second)
        assert (end_time - start_time) < 1.0, "Should complete quickly without infinite loop"

        # All models should be created
        assert len(models) == 4
        assert all(name in models for name in ["ModelA", "ModelB", "ModelC", "ModelD"])

        # Test that the dependency chain works
        ModelA = models["ModelA"]
        ModelB = models["ModelB"]
        ModelC = models["ModelC"]
        ModelD = models["ModelD"]

        d = ModelD(value="test")
        c = ModelC(d_ref=d)
        b = ModelB(c_ref=c)
        a = ModelA(b_ref=b)

        assert a.b_ref.c_ref.d_ref.value == "test"

    def test_unresolvable_dependencies_no_infinite_loop(self):
        """Test that models with unresolvable dependencies don't cause infinite loops."""
        yaml_content = """
data_models:
  - name: ModelA
    fields:
    - name: b_ref
      type: List[ModelB]
      desc: Reference to B list
  - name: ModelC
    fields:
    - name: value
      type: str
      desc: Simple value
"""

        # Note: ModelB is referenced but not defined
        parser = GemParser()

        import time

        start_time = time.time()

        # This should raise an exception for undefined ModelB
        with pytest.raises(TypeMappingError, match="Unknown type: ModelB"):
            parser.parse_from_yaml_string(yaml_content)

        end_time = time.time()

        # Should fail quickly (less than 1 second)
        assert (end_time - start_time) < 1.0, "Should fail quickly without infinite loop"

    def test_mixed_resolvable_unresolvable_no_infinite_loop(self):
        """Test mixed scenario with some resolvable and some unresolvable models."""
        yaml_content = """
data_models:
  - name: GoodModel
    fields:
    - name: value
      type: str
      desc: Simple field
  - name: AnotherGoodModel
    fields:
    - name: good_ref
      type: GoodModel
      desc: Reference to good model
  - name: BadModel
    fields:
    - name: bad_ref
      type: UndefinedModel
      desc: Reference to undefined model
"""

        parser = GemParser()

        import time

        start_time = time.time()

        # This should raise an exception for UndefinedModel
        with pytest.raises(TypeMappingError, match="Unknown type: UndefinedModel"):
            parser.parse_from_yaml_string(yaml_content)

        end_time = time.time()

        # Should fail quickly (less than 1 second)
        assert (end_time - start_time) < 1.0, "Should fail quickly without infinite loop"

    def test_self_reference_circular_detection(self):
        """Test that self-referencing models are properly detected as circular references."""
        yaml_content = """
data_models:
  - name: TreeNode
    fields:
    - name: value
      type: str
      desc: Node value
    - name: parent
      type: Optional[TreeNode]
      desc: Parent node
    - name: children
      type: List[TreeNode]
      desc: Child nodes
"""

        parser = GemParser()

        import time

        start_time = time.time()

        # This should raise CircularReferenceError quickly (not hang in infinite loop)
        with pytest.raises(CircularReferenceError, match="Circular reference detected involving model 'TreeNode'"):
            parser.parse_from_yaml_string(yaml_content)

        end_time = time.time()

        # Should fail quickly (less than 1 second) - no infinite loop
        assert (end_time - start_time) < 1.0, "Should detect circular reference quickly without infinite loop"

    def test_dependency_resolution_efficiency(self):
        """Test that dependency resolution is efficient and doesn't use excessive iterations."""
        yaml_content = """
data_models:
  - name: Level5
    fields:
    - name: value
      type: str
      desc: Final level
  - name: Level4
    fields:
    - name: next
      type: Level5
      desc: Next level
  - name: Level3
    fields:
    - name: next
      type: Level4
      desc: Next level
  - name: Level2
    fields:
    - name: next
      type: Level3
      desc: Next level
  - name: Level1
    fields:
    - name: next
      type: Level2
      desc: Next level
"""

        parser = GemParser()

        import time

        start_time = time.time()

        # This should complete successfully and efficiently
        models = parser.parse_from_yaml_string(yaml_content)

        end_time = time.time()

        # Should complete very quickly (less than 0.5 seconds for 5 levels)
        assert (end_time - start_time) < 0.5, f"Should complete efficiently, took {end_time - start_time:.3f}s"

        # All models should be created
        assert len(models) == 5
        expected_models = ["Level1", "Level2", "Level3", "Level4", "Level5"]
        assert all(name in models for name in expected_models)

    def test_force_rebuild_fallback_no_infinite_loop(self):
        """Test that the force rebuild fallback mechanism doesn't cause infinite loops."""
        # This test simulates a scenario where normal dependency resolution might struggle
        # but the force rebuild should handle it without infinite loops
        yaml_content = """
data_models:
  - name: IndependentModel
    fields:
    - name: value
      type: str
      desc: Simple independent model
  - name: ComplexModel
    fields:
    - name: simple_ref
      type: IndependentModel
      desc: Reference to simple model
    - name: data
      type: Dict[str, List[str]]
      desc: Complex nested type
"""

        parser = GemParser()

        import time

        start_time = time.time()

        # This should complete successfully without infinite loops
        models = parser.parse_from_yaml_string(yaml_content)

        end_time = time.time()

        # Should complete quickly (less than 1 second)
        assert (end_time - start_time) < 1.0, "Should complete quickly without infinite loop"

        # All models should be created
        assert len(models) == 2
        assert "IndependentModel" in models
        assert "ComplexModel" in models

        # Test that models work correctly
        IndependentModel = models["IndependentModel"]
        ComplexModel = models["ComplexModel"]

        simple = IndependentModel(value="test")
        complex_obj = ComplexModel(simple_ref=simple, data={"key": ["value1", "value2"]})

        assert complex_obj.simple_ref.value == "test"
        assert complex_obj.data["key"] == ["value1", "value2"]


if __name__ == "__main__":
    pytest.main([__file__])
