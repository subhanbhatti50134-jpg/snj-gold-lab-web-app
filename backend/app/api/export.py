import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.reports import apply_date_filter, validate_dates
from app.core.permissions import READ_ROLES, require_roles
from app.db.session import get_db
from app.models.party import Party
from app.models.product import Product
from app.models.transaction import Transaction
from app.services.parties import list_parties

router = APIRouter(prefix="/api/export", tags=["CSV Export"])

MAX_ROWS = 50_000

TransactionKind = Literal[
    "purchase",
    "sale",
    "sales_return",
    "stock_adjustment",
    "stock_transfer",
]


def _cell(value: object) -> str:
    """Format one CSV cell; neutralise Excel formula injection."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    text = str(value)
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def csv_response(filename: str, header: list[str], rows) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(cell) for cell in row])
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _phones(db: Session, transactions: list[Transaction]) -> dict[int, str]:
    party_ids = {t.party_id for t in transactions if t.party_id is not None}
    party_names = {t.party_name for t in transactions if t.party_name}
    by_id: dict[int, str] = {}
    by_name: dict[str, str] = {}
    if party_ids or party_names:
        parties = db.query(Party).filter(
            or_(Party.id.in_(party_ids), Party.name.in_(party_names))
        ).all()
        by_id = {p.id: p.phone for p in parties}
        by_name = {p.name: p.phone for p in parties}
    return {
        t.id: (
            by_id.get(t.party_id) or by_name.get(t.party_name) or ""
        )
        for t in transactions
    }


@router.get(
    "/transactions.csv",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def export_transactions(
    kind: TransactionKind | None = Query(default=None),
    status: Literal["active", "cancelled", "all"] = Query(default="active"),
    search: str | None = Query(default=None, min_length=1, max_length=160),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    location: str | None = Query(default=None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    validate_dates(date_from, date_to)

    query = db.query(Transaction)

    if search:
        term = f"%{search.strip()}%"
        query = query.join(Product, Product.id == Transaction.product_id).filter(
            (Transaction.reference.ilike(term))
            | (Transaction.party_name.ilike(term))
            | (Product.name.ilike(term))
            | (Product.sku.ilike(term))
        )

    if kind is not None:
        query = query.filter(Transaction.kind == kind)
    if status != "all":
        query = query.filter(Transaction.status == status)
    if location:
        query = query.filter(Transaction.location == location.strip())
    query = apply_date_filter(query, Transaction.transaction_date, date_from, date_to)

    rows = (
        query.order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(MAX_ROWS)
        .all()
    )
    products = {p.id: p for p in db.query(Product).all()}

    def values(t: Transaction):
        total = Decimal(str(t.total_amount))
        paid = Decimal(str(t.amount_paid))
        product = products.get(t.product_id)
        return [
            t.reference,
            t.kind,
            t.status,
            t.transaction_date,
            f"{product.name} ({product.sku})" if product else "",
            t.quantity_grams,
            t.rate_per_gram,
            t.charges,
            t.making_charge_type,
            t.making_charge_value,
            t.making_amount,
            total,
            paid,
            total - paid,
            t.party_name,
            t.location,
            t.created_by,
            t.created_at,
        ]

    return csv_response(
        f"transactions-{date.today().isoformat()}.csv",
        [
            "reference",
            "kind",
            "status",
            "date",
            "product",
            "quantity_grams",
            "rate_per_gram",
            "charges",
            "making_type",
            "making_value",
            "making_amount",
            "total",
            "paid",
            "remaining",
            "party",
            "location",
            "created_by",
            "created_at",
        ],
        [values(t) for t in rows],
    )


@router.get(
    "/outstanding.csv",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def export_outstanding(
    kind: str | None = Query(default=None, pattern="^(purchase|sale)$"),
    party_name: str | None = Query(default=None, max_length=160),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    validate_dates(date_from, date_to)

    query = db.query(Transaction).filter(
        Transaction.kind.in_(("purchase", "sale")),
        Transaction.status == "active",
        Transaction.total_amount > Transaction.amount_paid,
    )
    if kind:
        query = query.filter(Transaction.kind == kind)
    if party_name:
        query = query.filter(
            Transaction.party_name.ilike(f"%{party_name.strip()}%")
        )
    query = apply_date_filter(query, Transaction.transaction_date, date_from, date_to)

    rows = (
        query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(MAX_ROWS)
        .all()
    )
    phones = _phones(db, rows)

    def values(t: Transaction):
        total = Decimal(str(t.total_amount))
        paid = Decimal(str(t.amount_paid))
        return [
            t.reference,
            t.kind,
            t.party_name,
            phones.get(t.id, ""),
            total,
            paid,
            total - paid,
            t.transaction_date,
            t.location,
        ]

    return csv_response(
        f"outstanding-{date.today().isoformat()}.csv",
        [
            "reference",
            "kind",
            "party",
            "phone",
            "total",
            "paid",
            "remaining",
            "date",
            "location",
        ],
        [values(t) for t in rows],
    )


@router.get(
    "/parties.csv",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def export_parties(
    search: str | None = Query(default=None, min_length=1, max_length=160),
    kind: str | None = Query(default=None, pattern="^(customer|supplier|both)$"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    rows = list_parties(
        db, search=search, kind=kind, include_inactive=include_inactive
    )

    def values(p):
        return [
            p["id"],
            p["name"],
            p["kind"],
            p["phone"],
            p["address"],
            p["notes"],
            p["active"],
            p["receivable"],
            p["payable"],
            p["net"],
        ]

    return csv_response(
        f"parties-{date.today().isoformat()}.csv",
        [
            "id",
            "name",
            "kind",
            "phone",
            "address",
            "notes",
            "active",
            "receivable",
            "payable",
            "net",
        ],
        [values(p) for p in rows],
    )


@router.get(
    "/party-ledger.csv",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def export_party_ledger(
    party_name: str = Query(min_length=1, max_length=160),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    validate_dates(date_from, date_to)

    query = db.query(Transaction).filter(
        Transaction.party_name.ilike(party_name.strip()),
        Transaction.kind.in_(("purchase", "sale", "sales_return")),
        Transaction.status == "active",
    )
    query = apply_date_filter(query, Transaction.transaction_date, date_from, date_to)

    rows = (
        query.order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
        .limit(MAX_ROWS)
        .all()
    )

    def values(t: Transaction):
        total = Decimal(str(t.total_amount))
        paid = Decimal(str(t.amount_paid))
        return [
            t.transaction_date,
            t.reference,
            t.kind,
            t.party_name,
            t.quantity_grams,
            t.making_amount,
            total,
            paid,
            total - paid,
            t.location,
        ]

    return csv_response(
        f"ledger-{date.today().isoformat()}.csv",
        [
            "date",
            "reference",
            "kind",
            "party",
            "quantity_grams",
            "making_amount",
            "total",
            "paid",
            "remaining",
            "location",
        ],
        [values(t) for t in rows],
    )
