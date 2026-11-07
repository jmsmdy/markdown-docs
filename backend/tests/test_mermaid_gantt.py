"""Tests for the Gantt chart mermaid parser and differ."""
import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.gantt import (
    GanttDiagramDiffer,
    GanttDiagramModel,
    GanttDiagramParser,
    GanttSection,
    GanttTask,
)


@pytest.fixture
def parser():
    return GanttDiagramParser()


@pytest.fixture
def differ():
    return GanttDiagramDiffer()


BASIC_GANTT = """\
gantt
    title Project Plan
    dateFormat YYYY-MM-DD
    section Design
    Create mockups :done, 2024-01-01, 5d
    Review design :active, 2024-01-06, 3d
    section Development
    Implement API :crit, 2024-01-09, 10d
    Write tests :2024-01-19, 5d
"""

SIMPLE_GANTT = """\
gantt
    title Simple
    dateFormat YYYY-MM-DD
    section Phase 1
    Task A :done, 2024-01-01, 3d
    Task B :2024-01-04, 2d
"""


class TestCanParse:
    def test_can_parse(self, parser):
        assert parser.can_parse("gantt\n    title Test\n    section S1\n    T1 :done, 2024-01-01, 3d") is True

    def test_can_parse_minimal(self, parser):
        assert parser.can_parse("gantt\n    section S\n    T :1d") is True

    def test_cannot_parse_flowchart(self, parser):
        assert parser.can_parse("graph TD\n    A --> B") is False

    def test_cannot_parse_class(self, parser):
        assert parser.can_parse("classDiagram\n    class A {}") is False

    def test_cannot_parse_empty(self, parser):
        assert parser.can_parse("") is False

    def test_can_parse_with_leading_comments(self, parser):
        assert parser.can_parse("%% comment\ngantt\n    section S\n    T :1d") is True


class TestParseSectionsAndTasks:
    def test_parse_sections_and_tasks(self, parser):
        model = parser.parse(BASIC_GANTT)
        assert model.title == 'Project Plan'
        assert model.date_format == 'YYYY-MM-DD'
        assert len(model.sections) == 2

        design = model.sections[0]
        assert design.name == 'Design'
        assert len(design.tasks) == 2
        assert design.tasks[0].name == 'Create mockups'
        assert design.tasks[1].name == 'Review design'

        dev = model.sections[1]
        assert dev.name == 'Development'
        assert len(dev.tasks) == 2
        assert dev.tasks[0].name == 'Implement API'
        assert dev.tasks[1].name == 'Write tests'

    def test_parse_title_and_format(self, parser):
        model = parser.parse(BASIC_GANTT)
        assert model.title == 'Project Plan'
        assert model.date_format == 'YYYY-MM-DD'

    def test_parse_no_title(self, parser):
        source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 3d"
        model = parser.parse(source)
        assert model.title == ''


class TestParseTaskStatuses:
    def test_parse_task_statuses(self, parser):
        model = parser.parse(BASIC_GANTT)
        design = model.sections[0]
        assert design.tasks[0].status == 'done'
        assert design.tasks[1].status == 'active'

        dev = model.sections[1]
        assert dev.tasks[0].status == 'crit'
        assert dev.tasks[1].status == ''

    def test_parse_milestone_status(self, parser):
        source = "gantt\n    section S\n    Milestone :milestone, 2024-01-01, 0d"
        model = parser.parse(source)
        assert model.sections[0].tasks[0].status == 'milestone'

    def test_parse_combined_status(self, parser):
        source = "gantt\n    section S\n    Critical done :crit, done, 2024-01-01, 3d"
        model = parser.parse(source)
        task = model.sections[0].tasks[0]
        assert 'crit' in task.status
        assert 'done' in task.status


class TestDiffNoChanges:
    def test_diff_no_changes(self, parser, differ):
        model1 = parser.parse(SIMPLE_GANTT)
        model2 = parser.parse(SIMPLE_GANTT)
        result = differ.diff(model1, model2)
        assert result.has_changes is False
        assert result.annotated_source is None


class TestDiffAddedSection:
    def test_diff_added_section(self, parser, differ):
        old_source = """\
gantt
    title Plan
    dateFormat YYYY-MM-DD
    section Phase 1
    Task A :done, 2024-01-01, 3d
"""
        new_source = """\
gantt
    title Plan
    dateFormat YYYY-MM-DD
    section Phase 1
    Task A :done, 2024-01-01, 3d
    section Phase 2
    Task B :2024-01-04, 2d
"""
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[+]' in result.annotated_source
        assert 'Phase 2' in result.annotated_source

    def test_diff_added_section_via_structural_diff(self):
        old_source = "gantt\n    section S1\n    T1 :done, 2024-01-01, 3d"
        new_source = "gantt\n    section S1\n    T1 :done, 2024-01-01, 3d\n    section S2\n    T2 :2024-01-04, 2d"
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert 'S2' in result


class TestDiffRemovedSection:
    def test_diff_removed_section(self, parser, differ):
        old_source = """\
gantt
    title Plan
    dateFormat YYYY-MM-DD
    section Phase 1
    Task A :done, 2024-01-01, 3d
    section Phase 2
    Task B :2024-01-04, 2d
"""
        new_source = """\
gantt
    title Plan
    dateFormat YYYY-MM-DD
    section Phase 1
    Task A :done, 2024-01-01, 3d
"""
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[-]' in result.annotated_source
        assert 'Phase 2' in result.annotated_source


class TestDiffAddedTask:
    def test_diff_added_task(self, parser, differ):
        old_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 3d"
        new_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 3d\n    Task B :2024-01-04, 2d"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[+]' in result.annotated_source
        assert 'Task B' in result.annotated_source


class TestDiffRemovedTask:
    def test_diff_removed_task(self, parser, differ):
        old_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 3d\n    Task B :2024-01-04, 2d"
        new_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 3d"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[-]' in result.annotated_source
        assert 'Task B' in result.annotated_source


class TestDiffChangedTask:
    def test_diff_changed_task(self, parser, differ):
        old_source = "gantt\n    section S1\n    Task A :active, 2024-01-01, 3d"
        new_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 5d"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[~]' in result.annotated_source
        assert 'crit' in result.annotated_source

    def test_diff_changed_duration(self, parser, differ):
        old_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 3d"
        new_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 7d"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert '[~]' in result.annotated_source


class TestAnnotationValidSyntax:
    def test_annotation_valid_syntax(self, parser, differ):
        """Annotated output should start with gantt and be structurally valid."""
        old_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 3d"
        new_source = "gantt\n    section S1\n    Task A :done, 2024-01-01, 5d\n    Task B :active, 2024-01-06, 2d\n    section S2\n    Task C :2024-01-08, 3d"
        old_model = parser.parse(old_source)
        new_model = parser.parse(new_source)
        result = differ.diff(old_model, new_model)
        assert result.has_changes is True
        assert result.annotated_source.strip().startswith('gantt')
        # Should contain section markers
        assert 'section' in result.annotated_source


class TestGracefulFailure:
    def test_graceful_failure(self, parser):
        """Parser should handle malformed input without crashing."""
        source = "gantt\n    this is not valid gantt syntax\n    ~~~garbage~~~"
        model = parser.parse(source)
        assert isinstance(model, GanttDiagramModel)
        assert isinstance(model.sections, list)

    def test_graceful_failure_empty(self, parser):
        source = "gantt"
        model = parser.parse(source)
        assert isinstance(model, GanttDiagramModel)
        assert len(model.sections) == 0
        assert model.title == ''

    def test_graceful_failure_no_section(self, parser):
        """Tasks before any section should still be captured."""
        source = "gantt\n    Task A :done, 2024-01-01, 3d"
        model = parser.parse(source)
        assert isinstance(model, GanttDiagramModel)
        # Tasks before sections go into an unnamed section
        assert len(model.sections) == 1
        assert model.sections[0].tasks[0].name == 'Task A'
