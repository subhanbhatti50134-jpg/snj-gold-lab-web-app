
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import MANAGE_ROLES, READ_ROLES, require_roles
from app.db.session import get_db
from app.models.metal_rate import MetalRate
from app.schemas.rate import RateCreate, RateOut

router = APIRouter(prefix="/api/rates", tags=["Metal Rates"])


@router.post(
    "",
    response_model=RateOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
def create_rate(
    payload: RateCreate,
    db: Session = Depends(get_db),
):
    # Keep the previous rate history, but deactivate the old
    # rate for the same metal and purity.
    old_rates = db.scalars(
        select(MetalRate).where(
            MetalRate.metal == payload.metal,
            MetalRate.purity == payload.purity,
            MetalRate.active.is_(True),
        )
    ).all()

    for old_rate in old_rates:
        old_rate.active = False

    new_rate = MetalRate(**payload.model_dump())
    db.add(new_rate)
    db.commit()
    db.refresh(new_rate)

    return new_rate


@router.get(
    "",
    response_model=list[RateOut],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def list_rates(
    metal: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    statement = select(MetalRate).order_by(
        MetalRate.verified_at.desc(),
        MetalRate.id.desc(),
    )

    if metal is not None:
        if metal not in {"gold", "silver"}:
            raise HTTPException(
                status_code=422,
                detail="Metal must be gold or silver",
            )
        statement = statement.where(MetalRate.metal == metal)

    if active_only:
        statement = statement.where(MetalRate.active.is_(True))

    return db.scalars(statement).all()


@router.get(
    "/{rate_id}",
    response_model=RateOut,
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_rate(
    rate_id: int,
    db: Session = Depends(get_db),
):
    rate = db.get(MetalRate, rate_id)

    if rate is None:
        raise HTTPException(status_code=404, detail="Metal rate not found")

    return rate
