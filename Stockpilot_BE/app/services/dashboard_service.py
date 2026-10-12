"""Dashboard metrics. Definitions (also documented in the README):

  total_active_products   products with is_active = true
  low_stock_products      active products with stock_quantity <= low_stock_threshold
  order_counts_by_status  orders CREATED within the date range, per status
  order_value             sum(total_amount) of orders created in the range that are NOT cancelled
                          (PENDING + CONFIRMED + COMPLETED) - stock is reserved from PENDING on, so
                          these orders represent committed sales
  completed_order_value   same, restricted to COMPLETED orders
  recent_orders / recent_adjustments   latest 5 / 10 in the workspace, regardless of the range

The date range is inclusive, in UTC; the default is the last 30 days including today.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.context import WorkspaceContext
from app.domain.order_rules import OrderStatus
from app.repositories import inventory as inventory_repo
from app.repositories import orders as order_repo
from app.repositories import products as product_repo
from app.repositories.common import utc_bounds
from app.schemas.common import DateRange
from app.schemas.dashboard import DashboardOut, DateRangeOut
from app.schemas.inventory import AdjustmentOut
from app.schemas.order import OrderOut

DEFAULT_RANGE_DAYS = 30
RECENT_ORDERS = 5
RECENT_ADJUSTMENTS = 10


def build_dashboard(db: Session, ctx: WorkspaceContext, requested: DateRange) -> DashboardOut:
    date_to = requested.date_to or datetime.now(timezone.utc).date()
    date_from = requested.date_from or date_to - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    resolved = DateRange(date_from=date_from, date_to=date_to)  # re-validates from <= to
    start, end = utc_bounds(resolved)
    assert start is not None and end is not None

    return DashboardOut(
        range=DateRangeOut(date_from=date_from, date_to=date_to),
        total_active_products=product_repo.count_active(db, ctx.workspace_id),
        low_stock_products=product_repo.count_low_stock(db, ctx.workspace_id),
        order_counts_by_status=order_repo.counts_by_status(db, ctx.workspace_id, start, end),
        order_value=order_repo.value_in_range(db, ctx.workspace_id, start, end),
        completed_order_value=order_repo.value_in_range(
            db, ctx.workspace_id, start, end, statuses=(OrderStatus.COMPLETED,)
        ),
        recent_orders=[OrderOut.model_validate(o) for o in order_repo.recent(db, ctx.workspace_id, RECENT_ORDERS)],
        recent_adjustments=[
            AdjustmentOut.model_validate(a) for a in inventory_repo.recent(db, ctx.workspace_id, RECENT_ADJUSTMENTS)
        ],
    )
