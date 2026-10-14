from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.party import Party
from app.models.transaction import Transaction
from app.schemas.party import PartyCreate, PartyUpdate
from app.services.audit import log_audit

ZERO = Decimal("0.00")


def create_party(db: Session, payload: PartyCreate, username: str) -> Party:
    party = Party(**payload.model_dump())
    db.add(party)

    try:
        log_audit(
            db,
            username=username,
            action="party.create",
            entity_type="party",
            detail=party.name,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A party with this name already exists",
        ) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(party)
    return party


def update_party(
    db: Session,
    party_id: int,
    payload: PartyUpdate,
    username: str,
) -> Party:
    party = db.get(Party, party_id)

    if party is None:
        raise HTTPException(status_code=404, detail="Party not found")

    changes = payload.model_dump(exclude_unset=True)

    try:
        for field, value in changes.items():
            setattr(party, field, value)

        log_audit(
            db,
            username=username,
            action="party.update",
            entity_type="party",
            entity_id=party.id,
            detail=", ".join(sorted(changes)) or "no field changes",
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A party with this name already exists",
        ) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(party)
    return party


def _balances(db: Session) -> dict[int, dict[str, Decimal]]:
    """Receivable (customer owes us) and payable (we owe supplier).

    Both are computed from authoritative transaction totals only:
    receivable = sum(total - paid) for active sales, minus the value of
    active sales returns (a return reduces what the customer owes).
    payable     = sum(total - paid) for active purchases.
    Stock adjustments and transfers never affect money balances.
    """
    rows = db.execute(
        select(
            Transaction.party_id,
            Transaction.kind,
            func.coalesce(func.sum(Transaction.total_amount), 0),
            func.coalesce(func.sum(Transaction.amount_paid), 0),
        )
        .where(
            Transaction.status == "active",
            Transaction.kind.in_(("purchase", "sale", "sales_return")),
            Transaction.party_id.is_not(None),
        )
        .group_by(Transaction.party_id, Transaction.kind)
    ).all()

    balances: dict[int, dict[str, Decimal]] = {}

    for party_id, kind, total, paid in rows:
        entry = balances.setdefault(
            party_id, {"receivable": ZERO, "payable": ZERO}
        )
        remaining = Decimal(str(total)) - Decimal(str(paid))

        if kind == "sale":
            entry["receivable"] += remaining
        elif kind == "sales_return":
            entry["receivable"] -= remaining
        else:
            entry["payable"] += remaining

    return balances


def _balances_by_name(db: Session) -> dict[str, dict[str, Decimal]]:
    """Same calculation for legacy rows saved without a party_id."""
    rows = db.execute(
        select(
            func.lower(Transaction.party_name),
            Transaction.kind,
            func.coalesce(func.sum(Transaction.total_amount), 0),
            func.coalesce(func.sum(Transaction.amount_paid), 0),
        )
        .where(
            Transaction.status == "active",
            Transaction.kind.in_(("purchase", "sale", "sales_return")),
            Transaction.party_id.is_(None),
            Transaction.party_name != "",
        )
        .group_by(func.lower(Transaction.party_name), Transaction.kind)
    ).all()

    balances: dict[str, dict[str, Decimal]] = {}

    for name, kind, total, paid in rows:
        entry = balances.setdefault(
            name, {"receivable": ZERO, "payable": ZERO}
        )
        remaining = Decimal(str(total)) - Decimal(str(paid))

        if kind == "sale":
            entry["receivable"] += remaining
        elif kind == "sales_return":
            entry["receivable"] -= remaining
        else:
            entry["payable"] += remaining

    return balances


def _party_row(
    party: Party,
    by_id: dict[int, dict[str, Decimal]],
    by_name: dict[str, dict[str, Decimal]],
) -> dict:
    entry = by_id.get(party.id) or by_name.get(party.name.lower())
    receivable = entry["receivable"] if entry else ZERO
    payable = entry["payable"] if entry else ZERO

    return {
        "id": party.id,
        "name": party.name,
        "kind": party.kind,
        "phone": party.phone,
        "address": party.address,
        "notes": party.notes,
        "active": party.active,
        "created_at": party.created_at,
        "receivable": receivable,
        "payable": payable,
        "net": receivable - payable,
    }


def list_parties(
    db: Session,
    *,
    search: str | None = None,
    kind: str | None = None,
    include_inactive: bool = False,
) -> list[dict]:
    statement = select(Party)

    if not include_inactive:
        statement = statement.where(Party.active.is_(True))

    if kind:
        if kind not in {"customer", "supplier", "both"}:
            raise HTTPException(
                status_code=422,
                detail="kind must be customer, supplier or both",
            )
        statement = statement.where(
            (Party.kind == kind) | (Party.kind == "both")
        )

    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            Party.name.ilike(term) | Party.phone.ilike(term)
        )

    parties = db.scalars(statement.order_by(Party.name)).all()

    by_id = _balances(db)
    by_name = _balances_by_name(db)

    return [_party_row(party, by_id, by_name) for party in parties]


def get_party(db: Session, party_id: int) -> dict:
    party = db.get(Party, party_id)

    if party is None:
        raise HTTPException(status_code=404, detail="Party not found")

    return _party_row(party, _balances(db), _balances_by_name(db))
