"""Unit tests: pure business rules, no database required."""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.permissions import Permission, Role, has_permission
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.domain.inventory_rules import AdjustmentReason, manual_adjustment_problem
from app.domain.order_rules import (
    ALLOWED_TRANSITIONS,
    OrderStatus,
    can_transition,
    format_order_number,
    merge_items,
    parse_order_number,
    restores_stock,
)
from app.domain.pricing import line_total, money, order_total
from app.schemas.product import ProductCreate, ProductUpdate


# ---- pricing --------------------------------------------------------------------------------
def test_line_and_order_totals_use_exact_decimal_arithmetic():
    # 0.1 * 3 is 0.30000000000000004 with floats; with Decimal it is exactly 0.30
    assert line_total(Decimal("0.10"), 3) == Decimal("0.30")
    totals = [line_total(Decimal("19.99"), 3), line_total(Decimal("0.01"), 7)]
    assert totals == [Decimal("59.97"), Decimal("0.07")]
    assert order_total(totals) == Decimal("60.04")


def test_empty_order_total_is_zero():
    assert order_total([]) == Decimal("0.00")


def test_money_rounds_half_up():
    assert money("2.675") == Decimal("2.68")


# ---- order lifecycle ------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.PENDING, OrderStatus.CONFIRMED),
        (OrderStatus.CONFIRMED, OrderStatus.COMPLETED),
        (OrderStatus.PENDING, OrderStatus.CANCELLED),
        (OrderStatus.CONFIRMED, OrderStatus.CANCELLED),
    ],
)
def test_valid_transitions(current, target):
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.PENDING, OrderStatus.COMPLETED),  # cannot skip CONFIRMED
        (OrderStatus.CONFIRMED, OrderStatus.PENDING),  # no going back
        (OrderStatus.COMPLETED, OrderStatus.CANCELLED),
        (OrderStatus.COMPLETED, OrderStatus.CONFIRMED),
        (OrderStatus.CANCELLED, OrderStatus.CANCELLED),  # already cancelled
        (OrderStatus.CANCELLED, OrderStatus.CONFIRMED),
        (OrderStatus.PENDING, OrderStatus.PENDING),
    ],
)
def test_invalid_transitions(current, target):
    assert not can_transition(current, target)


def test_terminal_states_have_no_exits():
    assert ALLOWED_TRANSITIONS[OrderStatus.COMPLETED] == frozenset()
    assert ALLOWED_TRANSITIONS[OrderStatus.CANCELLED] == frozenset()


def test_only_cancellation_restores_stock():
    assert [s for s in OrderStatus if restores_stock(s)] == [OrderStatus.CANCELLED]


def test_duplicate_products_are_merged_by_summing_quantities():
    a, b = uuid.uuid4(), uuid.uuid4()
    assert merge_items([(a, 2), (b, 1), (a, 3)]) == {a: 5, b: 1}


def test_order_number_formatting_and_parsing():
    assert format_order_number(42) == "ORD-000042"
    assert parse_order_number("ORD-000042") == 42
    assert parse_order_number("ord-42") == 42
    assert parse_order_number("42") == 42
    assert parse_order_number("abc") is None


# ---- inventory adjustments ------------------------------------------------------------------
def test_manual_adjustment_rules():
    assert manual_adjustment_problem(AdjustmentReason.RECEIVED, 5, None) is None
    assert manual_adjustment_problem(AdjustmentReason.DAMAGED, -2, None) is None
    assert manual_adjustment_problem(AdjustmentReason.CORRECTION, -1, None) is None
    assert manual_adjustment_problem(AdjustmentReason.CORRECTION, 1, None) is None
    assert manual_adjustment_problem(AdjustmentReason.RECEIVED, 0, None)  # zero change
    assert manual_adjustment_problem(AdjustmentReason.RECEIVED, -3, None)  # received must add
    assert manual_adjustment_problem(AdjustmentReason.DAMAGED, 3, None)  # damaged must remove
    assert manual_adjustment_problem(AdjustmentReason.OTHER, 3, "  ")  # note required
    assert manual_adjustment_problem(AdjustmentReason.OTHER, 3, "recount") is None


@pytest.mark.parametrize("reason", [AdjustmentReason.ORDER_RESERVED, AdjustmentReason.ORDER_CANCELLED, AdjustmentReason.INITIAL_STOCK])
def test_system_reasons_cannot_be_chosen_manually(reason):
    assert manual_adjustment_problem(reason, 1, "x")


# ---- permissions ----------------------------------------------------------------------------
def test_owner_has_every_permission():
    assert all(has_permission(Role.OWNER, p) for p in Permission)


def test_staff_permissions_are_limited():
    allowed = {p for p in Permission if has_permission(Role.STAFF, p)}
    assert allowed == {
        Permission.PRODUCT_READ,
        Permission.INVENTORY_READ,
        Permission.INVENTORY_ADJUST,
        Permission.ORDER_READ,
        Permission.ORDER_CREATE,
        Permission.ORDER_UPDATE,
    }


# ---- input validation (schemas) -------------------------------------------------------------
def test_sku_is_normalised_to_uppercase_and_trimmed():
    product = ProductCreate(name="  Widget ", sku="  abc-1 ", unit_price="1.50")
    assert (product.name, product.sku) == ("Widget", "ABC-1")


@pytest.mark.parametrize("bad_price", ["-0.01", "1.234", "abc", "99999999999"])
def test_invalid_prices_are_rejected(bad_price):
    with pytest.raises(ValidationError):
        ProductCreate(name="W", sku="W1", unit_price=bad_price)


@pytest.mark.parametrize("field", ["stock_quantity", "low_stock_threshold"])
def test_negative_or_fractional_integers_are_rejected(field):
    for bad in (-1, 1.5):
        with pytest.raises(ValidationError):
            ProductCreate(name="W", sku="W1", unit_price="1.00", **{field: bad})


def test_product_update_rejects_direct_stock_edits():
    with pytest.raises(ValidationError):
        ProductUpdate(stock_quantity=99)


def test_product_update_cannot_null_required_fields():
    with pytest.raises(ValidationError):
        ProductUpdate(name=None)
    assert ProductUpdate(description=None).model_fields_set == {"description"}


# ---- security -------------------------------------------------------------------------------
def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("anything", None)  # unknown user path


def test_token_roundtrip_and_tampering():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id
    assert decode_access_token(token + "x") is None
    assert decode_access_token("not-a-token") is None
