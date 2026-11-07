"""Ranking basics of the manifest search (`pltr commands search`)."""

import pytest

from pltr.manifest import query_terms, score, search, suggest, words


def top(manifest, query, n=3):
    return [entry["path"] for entry in search(manifest["commands"], query)[:n]]


def entry(path, description="", sdk=(), generated=False, hidden=False):
    return {
        "path": path,
        "description": description,
        "help": description,
        "generated": generated,
        "hidden": hidden,
        "sdkMethods": list(sdk),
        "arguments": [],
        "options": [],
    }


def test_words_split_identifiers():
    assert words("datasets.Dataset.Branch.list") == [
        "datasets",
        "dataset",
        "branch",
        "list",
    ]
    assert words("get-current list_linked_objects SqlQuery") == [
        "get",
        "current",
        "list",
        "linked",
        "objects",
        "sql",
        "query",
    ]
    assert query_terms("how do I list the folders in pltr") == ["list", "folders"]
    assert query_terms("the") == ["the"]  # only stop words: keep them


def test_exact_command_path_ranks_first(manifest):
    assert top(manifest, "dataset get", 2) == [
        "pltr dataset get",
        "pltr api datasets dataset get",
    ]
    assert top(manifest, "pltr folder get", 1) == ["pltr folder get"]


def test_word_order_and_plurals_dont_matter(manifest):
    assert top(manifest, "list dataset branches", 1) == ["pltr dataset branches list"]
    assert top(manifest, "list folders", 1) == ["pltr folder list"]


def test_sdk_method_paths(manifest):
    assert set(top(manifest, "Dataset.Branch.list", 2)) == {
        "pltr dataset branches list",
        "pltr api datasets dataset branch list",
    }
    assert set(top(manifest, "FoundryClient.admin.User.get_current", 2)) == {
        "pltr admin user current",
        "pltr api admin user get-current",
    }
    assert query_terms("FoundryClient.admin.User.get_current") == [
        "admin",
        "user",
        "get",
        "current",
    ]


def test_curated_commands_rank_above_equal_generated_ones(manifest):
    assert top(manifest, "delete user", 2) == [
        "pltr admin user delete",
        "pltr api admin user delete",
    ]
    commands = [
        entry("pltr api things thing get", "Get a thing.", generated=True),
        entry("pltr thing get", "Get a thing."),
    ]
    paths = [e["path"] for e in search(commands, "thing get")]
    assert paths == ["pltr thing get", "pltr api things thing get"]


def test_verb_synonyms(manifest):
    assert "pltr sql execute" in top(manifest, "run sql query", 5)
    assert "pltr orchestration builds cancel" in top(manifest, "stop a build", 2)
    assert "pltr dataset files get" in top(manifest, "download file from dataset", 2)


def test_descriptions_and_help_match_too(manifest):
    assert "pltr admin user current" in top(manifest, "who am i current user", 2)
    assert "pltr resource-role grant" in top(manifest, "grant permission", 2)


def test_unmatched_words_lower_the_score():
    both = entry("pltr thing list", "List things.")
    assert score(both, "list things") > score(both, "list things zzzz") > 0


def test_no_match_and_hidden_commands(manifest):
    assert search(manifest["commands"], "zzzzqqqq") == []
    assert search(manifest["commands"], "") == []
    paths = top(manifest, "shell interactive", 10)
    assert "pltr shell interactive" not in paths  # hidden
    hidden = search(manifest["commands"], "shell interactive", include_hidden=True)
    assert "pltr shell interactive" in [e["path"] for e in hidden]


def test_search_is_deterministic(manifest):
    first = [e["path"] for e in search(manifest["commands"], "list")]
    assert first == [e["path"] for e in search(manifest["commands"], "list")]
    assert len(first) > 100


@pytest.mark.parametrize(
    "typo, expected",
    [
        ("dataset gett", "pltr dataset get"),
        ("pltr folder lst", "pltr folder list"),
        ("datasett", "pltr dataset"),
    ],
)
def test_suggestions_for_mistyped_paths(manifest, typo, expected):
    assert suggest(manifest, typo)[0] == expected
