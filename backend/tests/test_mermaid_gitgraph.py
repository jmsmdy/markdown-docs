"""
Tests for mermaid Git Graph diagram parser and differ.
"""
from __future__ import annotations

import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.gitgraph import (
    GitGraphDiffer,
    GitGraphModel,
    GitGraphParser,
    GitOperation,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

BASIC_GITGRAPH = """\
gitGraph
    commit
    commit id: "abc"
    commit tag: "v1.0"
    branch develop
    checkout develop
    commit
    commit id: "def"
    checkout main
    merge develop
"""

SIMPLE_GITGRAPH = """\
gitGraph
    commit
    commit
    commit
"""


@pytest.fixture
def parser():
    return GitGraphParser()


@pytest.fixture
def differ():
    return GitGraphDiffer()


# ── Parser tests ──────────────────────────────────────────────────────────────


class TestGitGraphCanParse:
    def test_can_parse(self, parser):
        assert parser.can_parse("gitGraph\n    commit") is True

    def test_can_parse_with_colon(self, parser):
        assert parser.can_parse("gitGraph:\n    commit") is True

    def test_cannot_parse_flowchart(self, parser):
        assert parser.can_parse("graph TD\n    A --> B") is False

    def test_cannot_parse_mindmap(self, parser):
        assert parser.can_parse("mindmap\n    root") is False


class TestGitGraphParse:
    def test_parse_commits(self, parser):
        model = parser.parse(SIMPLE_GITGRAPH)
        assert isinstance(model, GitGraphModel)
        assert len(model.operations) == 3
        assert all(op.type == "commit" for op in model.operations)

    def test_parse_commit_with_id(self, parser):
        model = parser.parse(BASIC_GITGRAPH)
        # Second operation is commit with id "abc"
        commit_abc = model.operations[1]
        assert commit_abc.type == "commit"
        assert commit_abc.id == "abc"

    def test_parse_commit_with_tag(self, parser):
        model = parser.parse(BASIC_GITGRAPH)
        # Third operation is commit with tag "v1.0"
        commit_tagged = model.operations[2]
        assert commit_tagged.type == "commit"
        assert commit_tagged.tag == "v1.0"

    def test_parse_branches(self, parser):
        model = parser.parse(BASIC_GITGRAPH)
        branch_ops = [op for op in model.operations if op.type == "branch"]
        assert len(branch_ops) == 1
        assert branch_ops[0].branch_name == "develop"

    def test_parse_checkout(self, parser):
        model = parser.parse(BASIC_GITGRAPH)
        checkout_ops = [op for op in model.operations if op.type == "checkout"]
        assert len(checkout_ops) == 2
        assert checkout_ops[0].branch_name == "develop"
        assert checkout_ops[1].branch_name == "main"

    def test_parse_merges(self, parser):
        model = parser.parse(BASIC_GITGRAPH)
        merge_ops = [op for op in model.operations if op.type == "merge"]
        assert len(merge_ops) == 1
        assert merge_ops[0].branch_name == "develop"

    def test_parse_cherry_pick(self, parser):
        source = """\
gitGraph
    commit id: "abc"
    branch feature
    checkout feature
    cherry-pick id: "abc"
"""
        model = parser.parse(source)
        cherry_ops = [op for op in model.operations if op.type == "cherry-pick"]
        assert len(cherry_ops) == 1
        assert cherry_ops[0].id == "abc"


# ── Differ tests ──────────────────────────────────────────────────────────────


class TestGitGraphDiff:
    def test_diff_no_changes(self, parser, differ):
        model1 = parser.parse(BASIC_GITGRAPH)
        model2 = parser.parse(BASIC_GITGRAPH)
        result = differ.diff(model1, model2)
        assert result.has_changes is False

    def test_diff_added_commits(self, parser, differ):
        old = SIMPLE_GITGRAPH
        new = """\
gitGraph
    commit
    commit
    commit
    commit
    commit
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "%% [+]" in result.annotated_source

    def test_diff_removed_commits(self, parser, differ):
        old = SIMPLE_GITGRAPH
        new = """\
gitGraph
    commit
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "%% [-]" in result.annotated_source

    def test_diff_added_branch(self, parser, differ):
        old = SIMPLE_GITGRAPH
        new = """\
gitGraph
    commit
    commit
    commit
    branch feature
    checkout feature
    commit
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "%% [+]" in result.annotated_source
        assert "branch feature" in result.annotated_source

    def test_diff_complex_changes(self, parser, differ):
        old = BASIC_GITGRAPH
        new = """\
gitGraph
    commit
    commit id: "abc"
    commit tag: "v2.0"
    branch develop
    branch feature
    checkout feature
    commit
    checkout develop
    commit
    checkout main
    merge develop
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        # Should contain both additions and removals
        assert "%% [+]" in result.annotated_source or "%% [-]" in result.annotated_source


# ── Integration tests ─────────────────────────────────────────────────────────


class TestGitGraphAnnotation:
    def test_annotation_valid_syntax(self, parser, differ):
        """Annotated source should still start with 'gitGraph' header."""
        old = SIMPLE_GITGRAPH
        new = """\
gitGraph
    commit
    commit
    commit
    branch feature
    checkout feature
    commit
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.annotated_source is not None
        lines = result.annotated_source.strip().splitlines()
        assert lines[0].strip() == "gitGraph"

    def test_mermaid_structural_diff_integration(self):
        """Test that gitgraph diffs work through the mermaid_structural_diff API."""
        old = SIMPLE_GITGRAPH
        new = """\
gitGraph
    commit
    commit
    commit
    branch feature
    checkout feature
    commit
"""
        result = mermaid_structural_diff(old, new)
        assert result is not None
        assert "gitGraph" in result
        assert "%% [+]" in result


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestGitGraphGracefulFailure:
    def test_graceful_failure(self, parser):
        """Parser should handle malformed input gracefully."""
        source = """\
gitGraph
    commit
    invalid_command something
    commit id: "valid"
"""
        model = parser.parse(source)
        assert isinstance(model, GitGraphModel)
        # Invalid line is skipped, valid ones parsed
        assert len(model.operations) == 2
        assert model.operations[0].type == "commit"
        assert model.operations[1].type == "commit"
        assert model.operations[1].id == "valid"

    def test_empty_source(self, parser):
        model = parser.parse("gitGraph")
        assert isinstance(model, GitGraphModel)
        assert model.operations == []
