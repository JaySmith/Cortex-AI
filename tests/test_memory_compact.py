"""Tests for the `cortex memory compact` command and its helpers."""

import json
from pathlib import Path

from typer.testing import CliRunner

from cortex.cli.main import (
    _cluster_notes,
    _content_words,
    _flag_conflict,
    _jaccard_words,
    _pair_score,
    _slug_root,
    app,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_memory_json(vault_root: Path, notes: dict, graph: dict | None = None) -> Path:
    """Write a memory.json into the vault's encoded directory."""
    encoded_dir = vault_root / "_sync" / "encoded"
    encoded_dir.mkdir(parents=True, exist_ok=True)
    path = encoded_dir / "memory.json"
    data = {
        "_meta": {"generated": "2026-01-01T00:00:00", "count": len(notes)},
        "notes": notes,
    }
    if graph is not None:
        data["_graph"] = graph
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


_TYPE_DIR = {
    "knowledge": "knowledge",
    "entity": "entities",
    "feedback": "feedback",
    "decision": "decisions",
    "log": "logs",
    "session": "logs",
}


def _create_note_file(vault_root: Path, note_id: str, note_type: str, body: str = "") -> Path:
    """Create a raw vault note .md file in the canonical type directory."""
    type_dir = vault_root / _TYPE_DIR.get(note_type, f"{note_type}s")
    type_dir.mkdir(parents=True, exist_ok=True)
    path = type_dir / f"{note_id}.md"
    path.write_text(
        f"---\nid: {note_id}\ntype: {note_type}\n---\n\n{body}\n", encoding="utf-8"
    )
    return path


def _note(
    nid, *, type="knowledge", category="", tier="core", tags=None, content="", updated="2026-01-01"
):
    return {
        "id": nid,
        "type": type,
        "category": category,
        "tier": tier,
        "tags": tags or [],
        "updated": updated,
        "aliases": [nid],
        "content": content,
    }


# ---------------------------------------------------------------------------
# Unit: _content_words / _jaccard_words
# ---------------------------------------------------------------------------


class TestJaccard:
    def test_identical_text_scores_one(self):
        assert _jaccard_words("the cat sat on the mat", "the cat sat on the mat") == 1.0

    def test_disjoint_text_scores_zero(self):
        assert _jaccard_words("alpha beta gamma", "delta epsilon zeta") == 0.0

    def test_empty_scores_zero(self):
        assert _jaccard_words("", "anything here") == 0.0
        assert _jaccard_words("anything here", "") == 0.0

    def test_partial_overlap_between_zero_and_one(self):
        score = _jaccard_words("jira workflow transition rules", "jira workflow status rules")
        assert 0.0 < score < 1.0

    def test_stop_words_ignored(self):
        # Only stop words in common -> no meaningful overlap.
        assert _jaccard_words("the and of database", "the and of pipeline") < 1.0

    def test_content_words_filters_short_and_stop(self):
        words = _content_words("The API is a REST service")
        assert "the" not in words  # stop word
        assert "is" not in words  # too short + stop
        assert "api" in words
        assert "rest" in words
        assert "service" in words


# ---------------------------------------------------------------------------
# Unit: _pair_score
# ---------------------------------------------------------------------------


class TestPairScore:
    def test_wiki_link_neighbor_adds_twenty(self):
        a = _note("a")
        b = _note("b")
        adjacency = {"a": ["b"], "b": ["a"]}
        score = _pair_score("a", a, "b", b, adjacency)
        # +20 link, +1 same type, +0 empty category
        assert score >= 20

    def test_shared_tags_scored(self):
        a = _note("a", tags=["jira", "workflow"])
        b = _note("b", tags=["jira", "workflow"])
        score = _pair_score("a", a, "b", b, {})
        # 2 shared tags * 4 = 8, +1 same type
        assert score >= 8

    def test_same_category_and_type(self):
        a = _note("a", category="patterns")
        b = _note("b", category="patterns")
        score = _pair_score("a", a, "b", b, {})
        assert score >= 4  # +3 category +1 type

    def test_content_overlap_capped_at_fifteen(self):
        shared = " ".join(f"word{i}" for i in range(100))
        a = _note("a", content=shared)
        b = _note("b", content=shared)
        score = _pair_score("a", a, "b", b, {})
        # identical content -> jaccard 1.0 -> +10 (round(1.0*10)); +1 same type
        assert score == 11

    def test_empty_category_not_matched(self):
        a = _note("a", category="")
        b = _note("b", category="")
        score = _pair_score("a", a, "b", b, {})
        # only +1 same type; empty categories must NOT count as a match
        assert score == 1


# ---------------------------------------------------------------------------
# Unit: _cluster_notes (single-linkage union-find)
# ---------------------------------------------------------------------------


class TestClustering:
    def test_transitive_clustering(self):
        # a~b, b~c => {a,b,c}
        pairs = {("a", "b"): 10, ("b", "c"): 10}
        clusters = _cluster_notes(["a", "b", "c", "d"], pairs, threshold=5)
        assert len(clusters) == 1
        assert set(clusters[0]) == {"a", "b", "c"}

    def test_below_threshold_excluded(self):
        pairs = {("a", "b"): 3}
        clusters = _cluster_notes(["a", "b"], pairs, threshold=5)
        assert clusters == []

    def test_singletons_dropped(self):
        pairs = {("a", "b"): 10}
        clusters = _cluster_notes(["a", "b", "c"], pairs, threshold=5)
        assert len(clusters) == 1
        assert set(clusters[0]) == {"a", "b"}

    def test_two_separate_clusters(self):
        pairs = {("a", "b"): 10, ("c", "d"): 10}
        clusters = _cluster_notes(["a", "b", "c", "d"], pairs, threshold=5)
        assert len(clusters) == 2


# ---------------------------------------------------------------------------
# Unit: _flag_conflict / _slug_root
# ---------------------------------------------------------------------------


class TestConflictHeuristics:
    def test_slug_root_strips_version_suffix(self):
        assert _slug_root("jira-workflow-2026") == "jira-workflow"
        assert _slug_root("api-notes-v2") == "api-notes"
        assert _slug_root("plain-note") == "plain-note"

    def test_shared_slug_root_flags_conflict(self):
        notes = {
            "jira-workflow": _note("jira-workflow"),
            "jira-workflow-2026": _note("jira-workflow-2026"),
        }
        assert _flag_conflict(["jira-workflow", "jira-workflow-2026"], notes) is True

    def test_same_cat_type_high_tag_overlap_flags(self):
        notes = {
            "a": _note("a", category="patterns", tags=["x", "y", "z"]),
            "b": _note("b", category="patterns", tags=["x", "y", "z"]),
        }
        assert _flag_conflict(["a", "b"], notes) is True

    def test_stale_sibling_flags(self):
        notes = {
            "a": _note("a", tags=["jira", "workflow"], updated="2026-01-01"),
            "b": _note("b", tags=["jira", "workflow"], updated="2026-06-01"),
        }
        assert _flag_conflict(["a", "b"], notes) is True

    def test_unrelated_pair_not_flagged(self):
        notes = {
            "a": _note("a", tags=["jira"], updated="2026-01-01"),
            "b": _note("b", tags=["python"], updated="2026-01-05"),
        }
        assert _flag_conflict(["a", "b"], notes) is False


# ---------------------------------------------------------------------------
# Integration: cortex memory compact
# ---------------------------------------------------------------------------


class TestCompactCommand:
    def test_no_clusters_reports_tidy(self, vault):
        _write_memory_json(
            vault,
            {
                "alpha": _note("alpha", tags=["one"], content="unrelated alpha content"),
                "beta": _note("beta", tags=["two"], content="totally different beta text"),
            },
        )
        result = runner.invoke(app, ["memory", "compact", "--vault", str(vault), "--yes"])
        assert result.exit_code == 0
        assert "tidy" in result.stdout.lower() or "no overlapping" in result.stdout.lower()

    def test_fewer_than_two_notes(self, vault):
        _write_memory_json(vault, {"only": _note("only")})
        result = runner.invoke(app, ["memory", "compact", "--vault", str(vault), "--yes"])
        assert result.exit_code == 0
        assert "nothing to compact" in result.stdout.lower()

    def test_dry_run_finds_cluster_no_writes(self, vault):
        notes = {
            "jira-a": _note(
                "jira-a", category="patterns", tags=["jira", "workflow"],
                content="jira workflow transition rules for status changes",
            ),
            "jira-b": _note(
                "jira-b", category="patterns", tags=["jira", "workflow"],
                content="jira workflow transition rules and status handling",
            ),
        }
        _write_memory_json(vault, notes)
        result = runner.invoke(
            app, ["memory", "compact", "--vault", str(vault), "--dry-run"]
        )
        assert result.exit_code == 0
        assert "Cluster 1" in result.stdout
        assert "dry run" in result.stdout.lower()
        # memory.json unchanged
        data = json.loads((vault / "_sync" / "encoded" / "memory.json").read_text())
        assert set(data["notes"].keys()) == {"jira-a", "jira-b"}

    def test_conflict_marker_shown(self, vault):
        notes = {
            "jira-workflow": _note(
                "jira-workflow", category="patterns", tags=["jira", "workflow", "rest"],
                content="original jira workflow rules content here",
            ),
            "jira-workflow-2026": _note(
                "jira-workflow-2026", category="patterns", tags=["jira", "workflow", "rest"],
                content="updated jira workflow rules content here for 2026",
            ),
        }
        _write_memory_json(vault, notes)
        result = runner.invoke(
            app, ["memory", "compact", "--vault", str(vault), "--dry-run"]
        )
        assert result.exit_code == 0
        assert "possible conflict" in result.stdout

    def test_threshold_option_suppresses_weak_clusters(self, vault):
        # Only +1 (same type) links these — well below a high threshold.
        notes = {
            "a": _note("a", content="apple orange banana"),
            "b": _note("b", content="car truck bicycle"),
        }
        _write_memory_json(vault, notes)
        result = runner.invoke(
            app, ["memory", "compact", "--vault", str(vault), "--threshold", "50", "--yes"]
        )
        assert result.exit_code == 0
        assert "no overlapping" in result.stdout.lower() or "tidy" in result.stdout.lower()

    def test_interactive_delete_removes_note(self, vault):
        notes = {
            "dup-a": _note(
                "dup-a", category="patterns", tags=["jira", "workflow"],
                content="jira workflow transition rules for status changes here",
            ),
            "dup-b": _note(
                "dup-b", category="patterns", tags=["jira", "workflow"],
                content="jira workflow transition rules for status changes there",
            ),
        }
        _write_memory_json(vault, notes)
        _create_note_file(vault, "dup-a", "knowledge", body="body a")
        _create_note_file(vault, "dup-b", "knowledge", body="body b")

        # Delete member B (labels are assigned A, B in cluster order).
        result = runner.invoke(
            app,
            ["memory", "compact", "--vault", str(vault)],
            input="dB\n",
        )
        assert result.exit_code == 0
        assert "Deleted" in result.stdout
        # One of the two files should be gone.
        remaining = list((vault / "knowledge").glob("dup-*.md"))
        assert len(remaining) == 1

    def test_interactive_keep_makes_no_changes(self, vault):
        notes = {
            "keep-a": _note(
                "keep-a", category="patterns", tags=["jira", "workflow"],
                content="jira workflow transition rules for status changes here",
            ),
            "keep-b": _note(
                "keep-b", category="patterns", tags=["jira", "workflow"],
                content="jira workflow transition rules for status changes there",
            ),
        }
        _write_memory_json(vault, notes)
        result = runner.invoke(
            app, ["memory", "compact", "--vault", str(vault)], input="k\n"
        )
        assert result.exit_code == 0
        assert "1 skipped" in result.stdout
        data = json.loads((vault / "_sync" / "encoded" / "memory.json").read_text())
        assert set(data["notes"].keys()) == {"keep-a", "keep-b"}

    def test_quit_stops_processing(self, vault):
        notes = {
            "q-a": _note(
                "q-a", category="patterns", tags=["jira", "workflow"],
                content="jira workflow transition rules for status changes here",
            ),
            "q-b": _note(
                "q-b", category="patterns", tags=["jira", "workflow"],
                content="jira workflow transition rules for status changes there",
            ),
        }
        _write_memory_json(vault, notes)
        result = runner.invoke(
            app, ["memory", "compact", "--vault", str(vault)], input="q\n"
        )
        assert result.exit_code == 0
        assert "Quitting" in result.stdout

    def test_missing_memory_json_errors(self, vault):
        # No memory.json written.
        result = runner.invoke(app, ["memory", "compact", "--vault", str(vault), "--yes"])
        assert result.exit_code == 1
