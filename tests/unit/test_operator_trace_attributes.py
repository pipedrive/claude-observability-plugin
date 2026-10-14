"""Pins the caller-supplied session id and trace metadata contract: values are
bounded to what the SDK propagates, bad input is ignored with a diagnostic, and
only the Langfuse session moves while hook state stays keyed on Claude's."""

import contextlib
from typing import Any

import pytest


def metadata(hook_module: Any, raw: str) -> dict:
    return hook_module.parse_operator_metadata(raw)[0]


def warning(hook_module: Any, raw: str) -> str:
    return hook_module.parse_operator_metadata(raw)[1]


# ----------------- session id -----------------

def test_a_session_id_is_taken_as_is(hook_module):
    assert hook_module.parse_operator_string("VAR", "  PROJ-123  ") == ("PROJ-123", "")


def test_no_session_id_and_no_warning_for_empty_input(hook_module):
    assert hook_module.parse_operator_string("VAR", "") == ("", "")
    assert hook_module.parse_operator_string("VAR", "   ") == ("", "")


def test_an_over_long_session_id_is_ignored_with_a_diagnostic(hook_module):
    raw = "x" * (hook_module.MAX_PROPAGATED_VALUE_CHARS + 1)

    value, diagnostic = hook_module.parse_operator_string("VAR", raw)

    # Ignored whole: a truncated id would merge unrelated sessions.
    assert value == ""
    assert diagnostic.startswith("VAR:")
    assert str(hook_module.MAX_PROPAGATED_VALUE_CHARS) in diagnostic


def test_a_non_ascii_session_id_is_ignored_with_a_diagnostic(hook_module):
    value, diagnostic = hook_module.parse_operator_string("VAR", "räkning")

    assert value == ""
    assert "US-ASCII" in diagnostic


# ----------------- metadata -----------------

def test_a_json_object_becomes_metadata(hook_module):
    raw = '{"github_actor": "octocat", "pr_number": 42, "dry_run": true}'

    assert metadata(hook_module, raw) == {
        "github_actor": "octocat",
        "pr_number": "42",
        "dry_run": "true",
    }


def test_null_and_blank_values_are_skipped_silently(hook_module):
    raw = '{"keep": "x", "pr_number": null, "blank": "  "}'

    assert hook_module.parse_operator_metadata(raw) == ({"keep": "x"}, "")


def test_no_metadata_and_no_warning_for_empty_input(hook_module):
    assert hook_module.parse_operator_metadata("") == ({}, "")
    assert hook_module.parse_operator_metadata("   ") == ({}, "")


def test_broken_json_is_ignored_with_a_diagnostic(hook_module):
    assert metadata(hook_module, '{"unclosed": ') == {}
    assert "not valid JSON" in warning(hook_module, '{"unclosed": ')


@pytest.mark.parametrize("raw", ['["a", "b"]', '"text"', "42"])
def test_json_that_is_not_an_object_is_ignored_with_a_diagnostic(hook_module, raw):
    assert metadata(hook_module, raw) == {}
    assert "not an object" in warning(hook_module, raw)


def test_a_non_scalar_value_is_dropped_with_a_diagnostic(hook_module):
    raw = '{"keep": "x", "inputs": {"nested": 1}, "list": [1]}'

    assert metadata(hook_module, raw) == {"keep": "x"}
    assert warning(hook_module, raw).count("non-scalar") == 1


def test_an_over_long_value_is_dropped_with_a_diagnostic(hook_module):
    raw = '{"keep": "x", "long": "%s"}' % ("y" * (hook_module.MAX_PROPAGATED_VALUE_CHARS + 1))

    assert metadata(hook_module, raw) == {"keep": "x"}
    assert str(hook_module.MAX_PROPAGATED_VALUE_CHARS) in warning(hook_module, raw)


def test_blank_and_non_ascii_keys_are_dropped_with_a_diagnostic(hook_module):
    raw = '{"keep": "x", " ": "y", "schlüssel": "z"}'

    assert metadata(hook_module, raw) == {"keep": "x"}
    assert "non-ASCII keys" in warning(hook_module, raw)


def test_keys_past_the_limit_are_dropped_with_a_diagnostic(hook_module):
    pairs = ", ".join(f'"k{i}": "v"' for i in range(hook_module.MAX_OPERATOR_METADATA_KEYS + 5))
    raw = "{" + pairs + "}"

    assert list(metadata(hook_module, raw)) == [f"k{i}" for i in range(hook_module.MAX_OPERATOR_METADATA_KEYS)]
    assert "past the first" in warning(hook_module, raw)


# ----------------- reaching the trace -----------------

@pytest.fixture
def propagate_calls(hook_module, monkeypatch: pytest.MonkeyPatch) -> list:
    calls: list = []

    @contextlib.contextmanager
    def recording_propagate(**kwargs: Any):
        calls.append(kwargs)
        yield

    monkeypatch.setattr(hook_module, "propagate_attributes", recording_propagate)
    return calls


def emit(hook_module: Any, fake_langfuse: Any, fixture_transcript_path: Any, **config: Any) -> None:
    hook_module.emit_new_turns_from_transcript(
        fake_langfuse,
        hook_module.LangfuseConfig("public", "secret", "https://example.test", "user-1", **config),
        "claude-session",
        fixture_transcript_path("simple_turn"),
    )


def test_the_caller_session_and_metadata_are_propagated(
    hook_module, fake_langfuse, isolated_hook_state, fixture_transcript_path, monkeypatch, propagate_calls
):
    monkeypatch.setattr(hook_module, "OPERATOR_SESSION_ID", "PROJ-123")
    monkeypatch.setattr(hook_module, "OPERATOR_METADATA", {"run_id": "7"})

    emit(hook_module, fake_langfuse, fixture_transcript_path)

    assert propagate_calls
    assert all(call["session_id"] == "PROJ-123" for call in propagate_calls)
    assert all(call["metadata"] == {"run_id": "7"} for call in propagate_calls)


def test_without_caller_values_the_claude_session_is_propagated(
    hook_module, fake_langfuse, isolated_hook_state, fixture_transcript_path, monkeypatch, propagate_calls
):
    monkeypatch.setattr(hook_module, "OPERATOR_SESSION_ID", "")
    monkeypatch.setattr(hook_module, "OPERATOR_METADATA", {})

    emit(hook_module, fake_langfuse, fixture_transcript_path)

    assert propagate_calls
    assert all(call["session_id"] == "claude-session" for call in propagate_calls)
    assert all(call["metadata"] is None for call in propagate_calls)


def test_the_caller_session_leaves_trace_ids_and_root_metadata_alone(
    hook_module, fake_langfuse, isolated_hook_state, fixture_transcript_path, monkeypatch, propagate_calls
):
    # Trace ids stay seeded from the Claude session, so a shared caller
    # session can never make two Claude sessions collide on one trace.
    seeds: list = []
    monkeypatch.setattr(
        fake_langfuse, "create_trace_id", lambda *, seed=None: seeds.append(seed) or "a" * 32
    )
    monkeypatch.setattr(hook_module, "OPERATOR_SESSION_ID", "PROJ-123")

    emit(hook_module, fake_langfuse, fixture_transcript_path)

    assert seeds and all(seed.startswith("claude-session:") for seed in seeds)
    roots = [o for o in fake_langfuse.observations if o.name == "Conversational Turn"]
    assert roots and all(root.kwargs["metadata"]["session_id"] == "claude-session" for root in roots)


def test_the_caller_trace_name_replaces_the_default(
    hook_module, fake_langfuse, isolated_hook_state, fixture_transcript_path, monkeypatch, propagate_calls
):
    monkeypatch.setattr(hook_module, "OPERATOR_TRACE_NAME", "AI Code Review")

    emit(hook_module, fake_langfuse, fixture_transcript_path)

    assert propagate_calls
    assert all(call["trace_name"] == "AI Code Review" for call in propagate_calls)


def test_without_a_caller_trace_name_the_default_is_kept(
    hook_module, fake_langfuse, isolated_hook_state, fixture_transcript_path, monkeypatch, propagate_calls
):
    monkeypatch.setattr(hook_module, "OPERATOR_TRACE_NAME", "")

    emit(hook_module, fake_langfuse, fixture_transcript_path)

    assert propagate_calls
    assert all(call["trace_name"] == hook_module.TRACE_NAME for call in propagate_calls)


def test_attached_mode_ignores_the_caller_trace_attributes(
    hook_module, fake_langfuse, isolated_hook_state, fixture_transcript_path, monkeypatch, propagate_calls
):
    monkeypatch.setattr(hook_module, "OPERATOR_SESSION_ID", "PROJ-123")
    monkeypatch.setattr(hook_module, "OPERATOR_METADATA", {"run_id": "7"})
    monkeypatch.setattr(hook_module, "OPERATOR_TRACE_NAME", "AI Code Review")

    emit(
        hook_module, fake_langfuse, fixture_transcript_path,
        parent_trace_id="1234567890abcdef1234567890abcdef", parent_span_id="fedcba0987654321",
    )

    assert propagate_calls == []


# ----------------- config precedence -----------------

def test_the_env_var_wins_over_the_wizard_option(hook_module, monkeypatch):
    monkeypatch.setenv("CC_LANGFUSE_SESSION_ID", "env:repo")
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_CC_LANGFUSE_SESSION_ID", "env:machine")

    assert hook_module._opt(hook_module.OPERATOR_SESSION_ID_VAR) == "env:repo"
