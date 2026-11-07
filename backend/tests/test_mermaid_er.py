"""Tests for the ER diagram mermaid parser and differ."""
import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.er import (
    ERAttribute,
    ERDiagramDiffer,
    ERDiagramModel,
    ERDiagramParser,
    EREntity,
    ERRelationship,
)


@pytest.fixture
def parser():
    return ERDiagramParser()


@pytest.fixture
def differ():
    return ERDiagramDiffer()


BASIC_ER_DIAGRAM = """\
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    CUSTOMER {
        string name PK
        string email
    }
    ORDER {
        int id PK
        string status
    }
"""

SIMPLE_ER = """\
erDiagram
    CUSTOMER ||--o{ ORDER : places
    CUSTOMER {
        string name PK
    }
    ORDER {
        int id PK
    }
"""


class TestCanParse:
    def test_can_parse(self, parser):
        assert parser.can_parse("erDiagram\n    CUSTOMER ||--o{ ORDER : places") is True

    def test_can_parse_case_insensitive(self, parser):
        assert parser.can_parse("erDiagram\n    A ||--|| B : rel") is True

    def test_cannot_parse_flowchart(self, parser):
        assert parser.can_parse("graph TD\n    A --> B") is False

    def test_cannot_parse_class(self, parser):
        assert parser.can_parse("classDiagram\n    class Foo {}") is False

    def test_cannot_parse_empty(self, parser):
        assert parser.can_parse("") is False

    def test_can_parse_with_leading_comments(self, parser):
        assert parser.can_parse("%% comment\nerDiagram\n    A ||--|| B : r") is True


class TestParseEntities:
    def test_parse_entities(self, parser):
        model = parser.parse(BASIC_ER_DIAGRAM)
        assert 'CUSTOMER' in model.entities
        assert 'ORDER' in model.entities
        assert 'LINE_ITEM' in model.entities

    def test_parse_entity_from_relationship(self, parser):
        source = "erDiagram\n    FOO ||--o{ BAR : has"
        model = parser.parse(source)
        assert 'FOO' in model.entities
        assert 'BAR' in model.entities


class TestParseRelationships:
    def test_parse_relationships(self, parser):
        model = parser.parse(BASIC_ER_DIAGRAM)
        assert len(model.relationships) == 2
        rel = model.relationships[0]
        assert rel.entity1 == 'CUSTOMER'
        assert rel.entity2 == 'ORDER'
        assert rel.label == 'places'
        assert rel.cardinality1 == '||'
        assert rel.cardinality2 == 'o{'

    def test_parse_relationship_various_cardinalities(self, parser):
        source = """\
erDiagram
    A ||--|| B : one_to_one
    C ||--o{ D : one_to_many
    E }o--o{ F : many_to_many
"""
        model = parser.parse(source)
        assert len(model.relationships) == 3
        assert model.relationships[0].cardinality1 == '||'
        assert model.relationships[0].cardinality2 == '||'
        assert model.relationships[1].cardinality1 == '||'
        assert model.relationships[1].cardinality2 == 'o{'
        assert model.relationships[2].cardinality1 == '}o'
        assert model.relationships[2].cardinality2 == 'o{'


class TestParseAttributes:
    def test_parse_attributes(self, parser):
        model = parser.parse(BASIC_ER_DIAGRAM)
        customer = model.entities['CUSTOMER']
        assert len(customer.attributes) == 2
        assert customer.attributes[0].type == 'string'
        assert customer.attributes[0].name == 'name'
        assert customer.attributes[0].keys == 'PK'
        assert customer.attributes[1].type == 'string'
        assert customer.attributes[1].name == 'email'
        assert customer.attributes[1].keys == ''

    def test_parse_attributes_with_multiple_keys(self, parser):
        source = "erDiagram\n    ENTITY {\n        int id PK\n        string ref FK\n    }"
        model = parser.parse(source)
        entity = model.entities['ENTITY']
        assert entity.attributes[0].keys == 'PK'
        assert entity.attributes[1].keys == 'FK'


class TestDiffNoChanges:
    def test_diff_no_changes(self, parser, differ):
        model1 = parser.parse(SIMPLE_ER)
        model2 = parser.parse(SIMPLE_ER)
        result = differ.diff(model1, model2)
        assert result.has_changes is False
        assert result.annotated_source is None


class TestDiffAddedEntity:
    def test_diff_added_entity(self, parser, differ):
        old_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }"
        new_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }\n    ORDER {\n        int id PK\n    }"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[+]' in result.annotated_source
        assert 'ORDER' in result.annotated_source

    def test_diff_added_entity_via_structural_diff(self):
        old_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }"
        new_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }\n    ORDER {\n        int id PK\n    }"
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert 'ORDER' in result


class TestDiffRemovedEntity:
    def test_diff_removed_entity(self, parser, differ):
        old_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }\n    ORDER {\n        int id PK\n    }"
        new_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[-]' in result.annotated_source
        assert 'ORDER' in result.annotated_source


class TestDiffAddedAttribute:
    def test_diff_added_attribute(self, parser, differ):
        old_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }"
        new_source = "erDiagram\n    CUSTOMER {\n        string name PK\n        string email\n    }"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[+]' in result.annotated_source
        assert 'email' in result.annotated_source


class TestDiffAddedRelationship:
    def test_diff_added_relationship(self, parser, differ):
        old_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }\n    ORDER {\n        int id PK\n    }"
        new_source = "erDiagram\n    CUSTOMER ||--o{ ORDER : places\n    CUSTOMER {\n        string name PK\n    }\n    ORDER {\n        int id PK\n    }"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[+]' in result.annotated_source


class TestDiffRemovedRelationship:
    def test_diff_removed_relationship(self, parser, differ):
        old_source = "erDiagram\n    CUSTOMER ||--o{ ORDER : places\n    CUSTOMER {\n        string name PK\n    }\n    ORDER {\n        int id PK\n    }"
        new_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }\n    ORDER {\n        int id PK\n    }"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[-]' in result.annotated_source


class TestAnnotationValidSyntax:
    def test_annotation_valid_syntax(self, parser, differ):
        """Annotated output should start with erDiagram and be structurally valid."""
        old_source = "erDiagram\n    CUSTOMER {\n        string name PK\n    }"
        new_source = "erDiagram\n    CUSTOMER {\n        string name PK\n        string email\n    }\n    ORDER {\n        int id PK\n    }\n    CUSTOMER ||--o{ ORDER : places"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert result.annotated_source.strip().startswith('erDiagram')
        # Should contain entity blocks
        assert '{' in result.annotated_source
        assert '}' in result.annotated_source


class TestGracefulFailure:
    def test_graceful_failure(self, parser):
        """Parser should handle malformed input without crashing."""
        source = "erDiagram\n    this is not valid ER syntax\n    ~~~garbage~~~"
        model = parser.parse(source)
        assert isinstance(model, ERDiagramModel)
        assert isinstance(model.entities, dict)
        assert isinstance(model.relationships, list)

    def test_graceful_failure_empty(self, parser):
        source = "erDiagram"
        model = parser.parse(source)
        assert isinstance(model, ERDiagramModel)
        assert len(model.entities) == 0

    def test_graceful_failure_unclosed_entity(self, parser):
        source = "erDiagram\n    CUSTOMER {\n        string name PK"
        model = parser.parse(source)
        assert isinstance(model, ERDiagramModel)
        # Should still capture what it can
        assert 'CUSTOMER' in model.entities
