import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require
from app.core.context import WorkspaceContext
from app.core.permissions import Permission
from app.domain.inventory_rules import AdjustmentReason
from app.schemas.common import DateRangeDep, Page, PageDep, make_page
from app.schemas.inventory import AdjustmentOut
from app.services import inventory_service

router = APIRouter(prefix="/workspaces/{workspace_id}/inventory", tags=["inventory"])


@router.get("/adjustments", response_model=Page[AdjustmentOut])
def list_adjustments(
    ctx: Annotated[WorkspaceContext, Depends(require(Permission.INVENTORY_READ))],
    db: DbSession,
    page: PageDep,
    dates: DateRangeDep,
    product_id: uuid.UUID | None = None,
    reason: AdjustmentReason | None = None,
) -> Page[AdjustmentOut]:
    """Workspace-wide stock history (newest first), including order reservations and restores."""
    rows, total = inventory_service.list_adjustments(db, ctx, page, dates, product_id=product_id, reason=reason)
    return make_page(rows, AdjustmentOut, total, page)
