from crow_technical_delta import (
    ChangeDirection,
    DeltaType,
    ValueKind,
    classify_direction,
    parse_quantity,
    structure_change,
)


def test_numeric_quantity_parsing() -> None:
    assert parse_quantity("12,5", ValueKind.NUMBER) == 12.5
    assert parse_quantity("12.5", ValueKind.TEXT) is None


def test_numeric_increase_is_structured() -> None:
    change = structure_change(
        DeltaType.MODIFIED,
        "5.0",
        "8.0",
        ValueKind.NUMBER,
    )

    assert change.baseline_quantity == 5.0
    assert change.approved_quantity == 8.0
    assert change.quantity_delta == 3.0
    assert change.direction == ChangeDirection.INCREASE


def test_numeric_decrease_is_structured() -> None:
    change = structure_change(
        DeltaType.MODIFIED,
        "8",
        "5",
        ValueKind.NUMBER,
    )

    assert change.quantity_delta == -3.0
    assert change.direction == ChangeDirection.DECREASE


def test_non_numeric_modified_value_is_generic_change() -> None:
    change = structure_change(
        DeltaType.MODIFIED,
        "EI30",
        "EI60",
        ValueKind.ENUM,
    )

    assert change.quantity_delta is None
    assert change.direction == ChangeDirection.CHANGED


def test_added_removed_and_unchanged_directions() -> None:
    assert classify_direction(DeltaType.ADDED, None, 1.0) == ChangeDirection.ADDED
    assert classify_direction(DeltaType.REMOVED, 1.0, None) == ChangeDirection.REMOVED
    assert classify_direction(DeltaType.UNCHANGED, 1.0, 1.0) == ChangeDirection.UNCHANGED
