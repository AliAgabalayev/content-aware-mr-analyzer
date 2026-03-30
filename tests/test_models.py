import pytest
from pydantic import ValidationError
from models import GitLabMRPayload


FULL_PAYLOAD = {
    "object_attributes": {
        "action": "merge",
        "state": "merged",
        "title": "[LT-42] Fix login redirect",
        "url": "http://gitlab.test/mr/1",
    },
    "commits": [
        {"message": "Fix OAuth callback\n\nDetails"},
        {"message": "Update session handling"},
    ],
}


def test_parses_full_payload():
    payload = GitLabMRPayload.model_validate(FULL_PAYLOAD)
    assert payload.object_attributes.action == "merge"
    assert payload.object_attributes.state == "merged"
    assert payload.object_attributes.title == "[LT-42] Fix login redirect"
    assert payload.object_attributes.url == "http://gitlab.test/mr/1"
    assert len(payload.commits) == 2
    assert payload.commits[0].message == "Fix OAuth callback\n\nDetails"


def test_commits_default_to_empty_list():
    payload = GitLabMRPayload.model_validate({
        "object_attributes": {
            "action": "open",
            "state": "opened",
            "title": "No commits here",
            "url": "http://gitlab.test/mr/2",
        }
    })
    assert payload.commits == []


def test_extra_fields_are_ignored():
    data = {
        "object_attributes": {
            **FULL_PAYLOAD["object_attributes"],
            "extra_field": "ignored",
        },
        "commits": FULL_PAYLOAD["commits"],
        "unknown_top_level": "ignored",
    }
    payload = GitLabMRPayload.model_validate(data)
    assert payload.object_attributes.action == "merge"


def test_missing_object_attributes_raises():
    with pytest.raises(ValidationError):
        GitLabMRPayload.model_validate({"commits": []})
