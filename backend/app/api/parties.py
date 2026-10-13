from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import MANAGE_ROLES, READ_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.party import PartyCreate, PartyOut, PartyUpdate
from app.services.parties import (
    create_party,
    get_party,
    list_parties,
    update_party,
)

router = APIRouter(prefix="/api/parties", tags=["Customers & Suppliers"])


@router.get(
    "",
    response_model=list[PartyOut],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_parties(
    search: str | None = Query(default=None, min_length=1, max_length=160),
    kind: str | None = Query(default=None, pattern="^(customer|supplier|both)$"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    return list_parties(
        db, search=search, kind=kind, include_inactive=include_inactive
    )


@router.post(
    "",
    response_model=PartyOut,
    status_code=status.HTTP_201_CREATED,
)
def add_party(
    payload: PartyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    party = create_party(db, payload, user.username)
    return get_party(db, party.id)


@router.patch(
    "/{party_id}",
    response_model=PartyOut,
)
def edit_party(
    party_id: int,
    payload: PartyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    update_party(db, party_id, payload, user.username)
    return get_party(db, party_id)
