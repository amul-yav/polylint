
import pytest

from polylint.fix.fixer import (
    Fix,
    FixError,
    Fixer,
    TextEdit,
)


@pytest.fixture
def fixer():
    return Fixer()


def test_text_edit_creation():
    edit = TextEdit(0, 3, "cat")

    assert edit.start == 0
    assert edit.end == 3
    assert edit.replacement == "cat"


def test_negative_start():
    with pytest.raises(ValueError):
        TextEdit(-1, 2, "x")


def test_invalid_range():
    with pytest.raises(ValueError):
        TextEdit(5, 2, "x")


def test_fix_creation():
    fix = Fix(
        "PL001",
        "Rename variable",
        (TextEdit(0, 3, "new"),),
    )

    assert fix.rule_id == "PL001"
    assert len(fix.edits) == 1


def test_empty_rule_id():
    with pytest.raises(ValueError):
        Fix("", "message", (TextEdit(0, 1, "x"),))


def test_empty_edits():
    with pytest.raises(ValueError):
        Fix("PL001", "message", ())


def test_replace_text(fixer):
    result = fixer.apply_edits(
        "hello world",
        [TextEdit(6, 11, "Python")],
    )

    assert result == "hello Python"


def test_insert_text(fixer):
    result = fixer.apply_edits(
        "hello",
        [TextEdit(5, 5, " world")],
    )

    assert result == "hello world"


def test_delete_text(fixer):
    result = fixer.apply_edits(
        "hello world",
        [TextEdit(5, 11, "")],
    )

    assert result == "hello"


def test_replace_entire_source(fixer):
    result = fixer.apply_edits(
        "old",
        [TextEdit(0, 3, "new")],
    )

    assert result == "new"


def test_empty_source(fixer):
    result = fixer.apply_edits(
        "",
        [TextEdit(0, 0, "hello")],
    )

    assert result == "hello"


def test_multiple_edits(fixer):
    source = "bad = 1\nprint(bad)"

    edits = [
        TextEdit(0, 3, "good"),
        TextEdit(14, 17, "good"),
    ]

    result = fixer.apply_edits(source, edits)

    assert result == "good = 1\nprint(good)"


def test_edits_applied_in_reverse_order(fixer):
    source = "abcdef"

    edits = [
        TextEdit(0, 1, "A"),
        TextEdit(5, 6, "F"),
    ]

    assert fixer.apply_edits(source, edits) == "AbcdeF"


def test_adjacent_edits(fixer):
    source = "abcd"

    edits = [
        TextEdit(0, 2, "AB"),
        TextEdit(2, 4, "CD"),
    ]

    assert fixer.apply_edits(source, edits) == "ABCD"


def test_overlapping_edits_raise_error(fixer):
    edits = [
        TextEdit(0, 3, "abc"),
        TextEdit(2, 4, "de"),
    ]

    with pytest.raises(FixError):
        fixer.apply_edits("abcdef", edits)


def test_duplicate_edits_raise_error(fixer):
    edits = [
        TextEdit(0, 2, "x"),
        TextEdit(0, 2, "y"),
    ]

    with pytest.raises(FixError):
        fixer.apply_edits("abcd", edits)


def test_edit_beyond_source_length(fixer):
    with pytest.raises(FixError):
        fixer.apply_edits(
            "abc",
            [TextEdit(0, 5, "x")],
        )


def test_apply_single_fix(fixer):
    fix = Fix(
        "PL001",
        "Rename variable",
        (TextEdit(0, 3, "cat"),),
    )

    assert fixer.apply_fix("dog", fix) == "cat"


def test_apply_multiple_fixes(fixer):
    fixes = [
        Fix("PL001", "First", (TextEdit(0, 3, "cat"),)),
        Fix("PL002", "Second", (TextEdit(4, 7, "fox"),)),
    ]

    assert fixer.apply_fixes("dog pig", fixes) == "cat fox"


def test_multiple_fixes_with_conflict(fixer):
    fixes = [
        Fix("PL001", "First", (TextEdit(0, 3, "cat"),)),
        Fix("PL002", "Second", (TextEdit(2, 4, "fox"),)),
    ]

    with pytest.raises(FixError):
        fixer.apply_fixes("abcdef", fixes)


def test_no_edits(fixer):
    assert fixer.apply_edits("hello", []) == "hello"


def test_original_source_unchanged(fixer):
    source = "hello"

    fixer.apply_edits(
        source,
        [TextEdit(0, 5, "world")],
    )

    assert source == "hello"


def test_apply_fix_does_not_mutate_fix(fixer):
    fix = Fix(
        "PL001",
        "Replace",
        (TextEdit(0, 3, "cat"),),
    )

    fixer.apply_fix("dog", fix)

    assert fix.edits == (TextEdit(0, 3, "cat"),)


def test_apply_fixes_empty_list(fixer):
    assert fixer.apply_fixes("hello", []) == "hello"
