from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require
from app.core.context import WorkspaceContext
from app.core.permissions import Permission
from app.schemas.common import DateRangeDep
from app.schemas.dashboard import DashboardOut
from app.services import dashboard_service

router = APIRouter(prefix="/workspaces/{workspace_id}/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(
    ctx: Annotated[WorkspaceContext, Depends(require(Permission.DASHBOARD_READ))],
    db: DbSession,
    dates: DateRangeDep,
) -> DashboardOut:
    """Metrics for the workspace. Defaults to the last 30 days (UTC) when no range is given."""
    return dashboard_service.build_dashboard(db, ctx, dates)
