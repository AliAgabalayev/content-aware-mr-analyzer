from models import Commit, GitLabMRPayload, MRAttributes
from handlers.gitlab import (
    extract_commit_subjects,
    extract_task_id,
    is_merge_action,
    is_merge_request_hook,
    strip_title_prefix,
    validate_token,
)


# validate_token

def test_validate_token_matches():
    assert validate_token("abc123", "abc123") is True

def test_validate_token_mismatch():
    assert validate_token("wrong", "abc123") is False

def test_validate_token_none():
    assert validate_token(None, "abc123") is False


# is_merge_request_hook

def test_is_merge_request_hook_correct():
    assert is_merge_request_hook("Merge Request Hook") is True

def test_is_merge_request_hook_wrong():
    assert is_merge_request_hook("Push Hook") is False

def test_is_merge_request_hook_none():
    assert is_merge_request_hook(None) is False


# is_merge_action

def _make_payload(action: str, state: str) -> GitLabMRPayload:
    return GitLabMRPayload(
        object_attributes=MRAttributes(
            action=action, state=state, title="[LT-1] Test", url="http://x"
        )
    )

def test_is_merge_action_true():
    assert is_merge_action(_make_payload("merge", "merged")) is True

def test_is_merge_action_wrong_action():
    assert is_merge_action(_make_payload("open", "merged")) is False

def test_is_merge_action_wrong_state():
    assert is_merge_action(_make_payload("merge", "opened")) is False


# extract_task_id

def test_extract_task_id_standard():
    assert extract_task_id("[LT-42] Fix login") == 42

def test_extract_task_id_large_number():
    assert extract_task_id("[LT-1234] Something") == 1234

def test_extract_task_id_no_match():
    assert extract_task_id("Fix login redirect") is None

def test_extract_task_id_wrong_format():
    assert extract_task_id("[LT-abc] Bad ID") is None


# strip_title_prefix

def test_strip_title_prefix_with_space():
    assert strip_title_prefix("[LT-42] Fix login") == "Fix login"

def test_strip_title_prefix_no_space():
    assert strip_title_prefix("[LT-42]Fix login") == "Fix login"

def test_strip_title_prefix_large_id():
    assert strip_title_prefix("[LT-1234] Something") == "Something"


# extract_commit_subjects

def test_extract_commit_subjects_single_line():
    assert extract_commit_subjects([Commit(message="Fix bug")]) == ["Fix bug"]

def test_extract_commit_subjects_multiline():
    assert extract_commit_subjects(
        [Commit(message="Fix bug\n\nDetailed explanation")]
    ) == ["Fix bug"]

def test_extract_commit_subjects_multiple():
    commits = [Commit(message="First fix\nDetails"), Commit(message="Second fix")]
    assert extract_commit_subjects(commits) == ["First fix", "Second fix"]

def test_extract_commit_subjects_empty():
    assert extract_commit_subjects([]) == []
