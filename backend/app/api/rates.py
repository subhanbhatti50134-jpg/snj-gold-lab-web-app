
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import MANAGE_ROLES, READ_ROLES, require_roles
from app.db.session import get_db
from app.models.metal_rate import MetalRate
from app.models.user import User
from app.schemas.rate import RateCreate, RateOut
from app.services.audit import log_audit
from app.services.pricing import normalize_rate

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
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    # Convert the entered rate (per gram/tola/kilogram) to the single
    # internal unit: a rate per gram. Both values are stored so the
    # history shows exactly what the operator typed.
    try:
        per_gram = normalize_rate(payload.rate_per_gram, payload.unit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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

    new_rate = MetalRate(
        metal=payload.metal,
        purity=payload.purity,
        rate_per_gram=per_gram,
        unit=payload.unit,
        entered_rate=payload.rate_per_gram,
        source_note=payload.source_note,
        verified_by=payload.verified_by,
        active=True,
    )
    db.add(new_rate)

    log_audit(
        db,
        username=user.username,
        action="rate.create",
        entity_type="metal_rate",
        detail=(
            f"{payload.metal} {payload.purity}%: "
            f"{payload.rate_per_gram} per {payload.unit} "
            f"(= {per_gram} per gram)"
        ),
    )
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
