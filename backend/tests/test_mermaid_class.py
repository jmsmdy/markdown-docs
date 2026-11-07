"""Tests for the class diagram mermaid parser and differ."""
import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.class_diagram import (
    ClassDiagramDiffer,
    ClassDiagramModel,
    ClassDiagramParser,
    ClassInfo,
    ClassRelationship,
)


@pytest.fixture
def parser():
    return ClassDiagramParser()


@pytest.fixture
def differ():
    return ClassDiagramDiffer()


BASIC_CLASS_DIAGRAM = """\
classDiagram
    class Animal {
        +String name
        +int age
        +makeSound()
        +move()
    }
    class Dog {
        +String breed
        +bark()
    }
    Animal <|-- Dog : inherits
"""

SIMPLE_DIAGRAM = """\
classDiagram
    class Foo {
        +int x
        +doStuff()
    }
    class Bar {
        +String y
    }
    Foo --> Bar : uses
"""


class TestCanParse:
    def test_can_parse(self, parser):
        assert parser.can_parse("classDiagram\n    class Foo {}") is True

    def test_can_parse_case_insensitive(self, parser):
        assert parser.can_parse("classDiagram\n    class A {}") is True

    def test_cannot_parse_flowchart(self, parser):
        assert parser.can_parse("graph TD\n    A --> B") is False

    def test_cannot_parse_er(self, parser):
        assert parser.can_parse("erDiagram\n    CUSTOMER ||--o{ ORDER : places") is False

    def test_cannot_parse_empty(self, parser):
        assert parser.can_parse("") is False

    def test_can_parse_with_leading_comments(self, parser):
        assert parser.can_parse("%% comment\nclassDiagram\n    class A {}") is True


class TestParseClassesWithMembers:
    def test_parse_classes_with_members(self, parser):
        model = parser.parse(BASIC_CLASS_DIAGRAM)
        assert 'Animal' in model.classes
        assert 'Dog' in model.classes

        animal = model.classes['Animal']
        assert '+String name' in animal.members
        assert '+int age' in animal.members
        assert '+makeSound()' in animal.methods
        assert '+move()' in animal.methods

        dog = model.classes['Dog']
        assert '+String breed' in dog.members
        assert '+bark()' in dog.methods

    def test_parse_inline_member(self, parser):
        source = "classDiagram\n    Foo : +int x\n    Foo : +doStuff()"
        model = parser.parse(source)
        assert 'Foo' in model.classes
        assert '+int x' in model.classes['Foo'].members
        assert '+doStuff()' in model.classes['Foo'].methods

    def test_parse_empty_class(self, parser):
        source = "classDiagram\n    class EmptyClass {\n    }"
        model = parser.parse(source)
        assert 'EmptyClass' in model.classes
        assert model.classes['EmptyClass'].members == []
        assert model.classes['EmptyClass'].methods == []


class TestParseRelationships:
    def test_parse_relationships(self, parser):
        model = parser.parse(BASIC_CLASS_DIAGRAM)
        assert len(model.relationships) == 1
        rel = model.relationships[0]
        assert rel.from_class == 'Animal'
        assert rel.to_class == 'Dog'
        assert rel.rel_type == '<|--'
        assert rel.label == 'inherits'

    def test_parse_multiple_relationship_types(self, parser):
        source = """\
classDiagram
    ClassA <|-- ClassB
    ClassA *-- ClassC
    ClassA o-- ClassD
    ClassA --> ClassE : uses
    ClassA -- ClassF
    ClassA ..> ClassG : depends
    ClassA ..|> ClassH
"""
        model = parser.parse(source)
        assert len(model.relationships) == 7
        types = [r.rel_type for r in model.relationships]
        assert '<|--' in types
        assert '*--' in types
        assert 'o--' in types
        assert '-->' in types
        assert '--' in types
        assert '..>' in types
        assert '..|>' in types

    def test_relationship_creates_classes(self, parser):
        source = "classDiagram\n    A --> B : link"
        model = parser.parse(source)
        assert 'A' in model.classes
        assert 'B' in model.classes


class TestDiffNoChanges:
    def test_diff_no_changes(self, parser, differ):
        model1 = parser.parse(SIMPLE_DIAGRAM)
        model2 = parser.parse(SIMPLE_DIAGRAM)
        result = differ.diff(model1, model2)
        assert result.has_changes is False
        assert result.annotated_source is None


class TestDiffAddedClass:
    def test_diff_added_class(self, parser, differ):
        old_source = """\
classDiagram
    class Foo {
        +int x
    }
"""
        new_source = """\
classDiagram
    class Foo {
        +int x
    }
    class Bar {
        +String y
    }
"""
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[+]' in result.annotated_source
        assert 'Bar' in result.annotated_source

    def test_diff_added_class_via_structural_diff(self):
        old_source = "classDiagram\n    class Foo {\n        +int x\n    }"
        new_source = "classDiagram\n    class Foo {\n        +int x\n    }\n    class Bar {\n        +String y\n    }"
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert 'Bar' in result


class TestDiffRemovedClass:
    def test_diff_removed_class(self, parser, differ):
        old_source = """\
classDiagram
    class Foo {
        +int x
    }
    class Bar {
        +String y
    }
"""
        new_source = """\
classDiagram
    class Foo {
        +int x
    }
"""
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[-]' in result.annotated_source
        assert 'Bar' in result.annotated_source


class TestDiffAddedMember:
    def test_diff_added_member(self, parser, differ):
        old_source = "classDiagram\n    class Foo {\n        +int x\n    }"
        new_source = "classDiagram\n    class Foo {\n        +int x\n        +int y\n    }"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[+]' in result.annotated_source
        assert '+int y' in result.annotated_source


class TestDiffRemovedMember:
    def test_diff_removed_member(self, parser, differ):
        old_source = "classDiagram\n    class Foo {\n        +int x\n        +int y\n    }"
        new_source = "classDiagram\n    class Foo {\n        +int x\n    }"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[-]' in result.annotated_source
        assert '+int y' in result.annotated_source


class TestDiffAddedRelationship:
    def test_diff_added_relationship(self, parser, differ):
        old_source = "classDiagram\n    class A\n    class B"
        new_source = "classDiagram\n    class A\n    class B\n    A --> B : uses"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[+]' in result.annotated_source
        assert 'A' in result.annotated_source
        assert 'B' in result.annotated_source


class TestDiffRemovedRelationship:
    def test_diff_removed_relationship(self, parser, differ):
        old_source = "classDiagram\n    class A\n    class B\n    A --> B : uses"
        new_source = "classDiagram\n    class A\n    class B"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[-]' in result.annotated_source


class TestAnnotationValidSyntax:
    def test_annotation_valid_syntax(self, parser, differ):
        """Annotated output should still be parseable as a classDiagram."""
        old_source = "classDiagram\n    class Foo {\n        +int x\n    }"
        new_source = "classDiagram\n    class Foo {\n        +int x\n        +int y\n    }\n    class Bar {\n        +String z\n    }\n    Foo --> Bar : uses"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        # The annotated source should start with classDiagram
        assert result.annotated_source.strip().startswith('classDiagram')
        # Style lines should be present for highlighted classes
        assert 'style' in result.annotated_source


class TestGracefulFailure:
    def test_graceful_failure(self, parser):
        """Parser should handle malformed input without crashing."""
        # Completely invalid content
        source = "classDiagram\n    this is not valid syntax\n    ~~~garbage~~~"
        model = parser.parse(source)
        assert isinstance(model, ClassDiagramModel)
        # Should just have an empty or minimal model
        assert isinstance(model.classes, dict)
        assert isinstance(model.relationships, list)

    def test_graceful_failure_empty(self, parser):
        source = "classDiagram"
        model = parser.parse(source)
        assert isinstance(model, ClassDiagramModel)
        assert len(model.classes) == 0

    def test_graceful_failure_unclosed_block(self, parser):
        source = "classDiagram\n    class Foo {\n        +int x"
        model = parser.parse(source)
        assert isinstance(model, ClassDiagramModel)
        # Should still capture what it can
        assert 'Foo' in model.classes
