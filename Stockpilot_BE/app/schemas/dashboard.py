from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.inventory import AdjustmentOut
from app.schemas.order import OrderOut


class DateRangeOut(BaseModel):
    date_from: date
    date_to: date


class DashboardOut(BaseModel):
    range: DateRangeOut
    total_active_products: int
    low_stock_products: int
    # Orders CREATED inside the range, counted per status (every status is present, zero-filled).
    order_counts_by_status: dict[str, int]
    # Sum of total_amount of orders created in the range with status PENDING/CONFIRMED/COMPLETED.
    order_value: Decimal
    # Same, but COMPLETED orders only.
    completed_order_value: Decimal
    recent_orders: list[OrderOut]
    recent_adjustments: list[AdjustmentOut]
