
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.order import LayawayOrder
from app.models.party import Party
from app.models.product import Product
from app.models.transaction import Transaction
from app.schemas.order import OrderCreate, OrderDeliver, OrderUpdate
from app.schemas.transaction import TransactionCreate
from app.services.audit import log_audit
from app.services.pricing import money
from app.services.transactions import create_transaction


def _resolve_party(
    db: Session, party_id: int | None, party_name: str
) -> tuple[int | None, str]:
    if party_id is None:
        return None, party_name.strip()

    party = db.get(Party, party_id)
    if party is None or not party.active:
        raise HTTPException(status_code=404, detail="Active party not found")
    return party.id, party.name



def create_order(
    db: Session,
    payload: OrderCreate,
    username: str,
) -> LayawayOrder:
    party_id, party_name = _resolve_party(db, payload.party_id, payload.party_name)

    total = money(payload.estimated_weight_grams * payload.agreed_rate_per_gram)
    if payload.advance_amount > total:
        raise HTTPException(
            status_code=422,
            detail="Advance cannot exceed the estimated total",
        )

    order = LayawayOrder(
        reference=f"ORD-{uuid4().hex[:12].upper()}",
        party_id=party_id,
        party_name=party_name,
        description=payload.description.strip(),
        estimated_weight_grams=payload.estimated_weight_grams,
        agreed_rate_per_gram=payload.agreed_rate_per_gram,
        estimated_total=total,
        advance_amount=payload.advance_amount,
        status="pending",
        due_date=payload.due_date,
        notes=payload.notes,
        created_by=username,
    )

    db.add(order)
    db.flush()

    log_audit(
        db,
        username=username,
        action="order.create",
        entity_type="layaway_order",
        entity_id=order.id,
        detail=(
            f"{order.reference}; {order.description}; "
            f"{order.estimated_weight_grams}g; total {total}; "
            f"advance {payload.advance_amount}"
        ),
    )
    return order


def update_order(
    db: Session,
    order: LayawayOrder,
    payload: OrderUpdate,
    username: str,
) -> LayawayOrder:
    if order.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending orders can be edited",
        )

    total = money(payload.estimated_weight_grams * payload.agreed_rate_per_gram)
    if order.advance_amount > total:
        raise HTTPException(
            status_code=422,
            detail="New terms would drop below the advance already paid",
        )

    order.description = payload.description.strip()
    order.estimated_weight_grams = payload.estimated_weight_grams
    order.agreed_rate_per_gram = payload.agreed_rate_per_gram
    order.estimated_total = total
    order.due_date = payload.due_date
    order.notes = payload.notes
    db.flush()

    log_audit(
        db,
        username=username,
        action="order.update",
        entity_type="layaway_order",
        entity_id=order.id,
        detail=f"{order.reference}; terms updated; total {total}",
    )
    return order


def add_advance(
    db: Session,
    order: LayawayOrder,
    amount,
    username: str,
) -> LayawayOrder:
    if order.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Advances apply to pending orders only",
        )

    new_advance = Decimal(str(order.advance_amount)) + amount
    if new_advance > Decimal(str(order.estimated_total)):
        raise HTTPException(
            status_code=422,
            detail="Advance cannot exceed the estimated total",
        )

    order.advance_amount = new_advance
    db.flush()

    log_audit(
        db,
        username=username,
        action="order.advance",
        entity_type="layaway_order",
        entity_id=order.id,
        detail=(
            f"{order.reference}; +{amount}; "
            f"advance now {new_advance}"
        ),
    )
    return order


def deliver_order(
    db: Session,
    order: LayawayOrder,
    payload: OrderDeliver,
    username: str,
) -> tuple[LayawayOrder, Transaction]:
    if order.status == "delivered":
        raise HTTPException(status_code=409, detail="Order already delivered")
    if order.status == "cancelled":
        raise HTTPException(
            status_code=409, detail="Order is cancelled and cannot be delivered"
        )

    product = db.get(Product, payload.product_id)
    if product is None or not product.active:
        raise HTTPException(status_code=404, detail="Active product not found")

    weight = payload.actual_weight_grams or order.estimated_weight_grams
    total = money(weight * order.agreed_rate_per_gram)
    paid = min(Decimal(str(order.advance_amount)), total)

    sale_payload = TransactionCreate(
        product_id=product.id,
        party_id=order.party_id,
        quantity_grams=weight,
        gross_weight_grams=weight,
        net_weight_grams=weight,
        deduction_grams=Decimal("0"),
        purity=product.purity,
        rate_per_gram=order.agreed_rate_per_gram,
        rate_unit="gram",
        charges=Decimal("0"),
        amount_paid=paid,
        payment_method="cash",
        party_name=order.party_name,
        location=payload.location,
        notes=f"Bayana {order.reference}: {order.description}",
        created_by=username,
    )

    # Atomic: the sale is only kept if the order flips to delivered.
    sale = create_transaction(db, sale_payload, "sale", commit=False)

    order.status = "delivered"
    order.sale_id = sale.id
    order.delivered_at = datetime.now(UTC)
    db.flush()

    log_audit(
        db,
        username=username,
        action="order.deliver",
        entity_type="layaway_order",
        entity_id=order.id,
        detail=(
            f"{order.reference}; delivered as {sale.reference}; "
            f"{weight}g; total {total}; advance applied {paid}"
        ),
    )
    return order, sale


def cancel_order(
    db: Session,
    order: LayawayOrder,
    reason: str,
    username: str,
) -> LayawayOrder:
    if order.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending orders can be cancelled",
        )

    order.status = "cancelled"
    db.flush()

    log_audit(
        db,
        username=username,
        action="order.cancel",
        entity_type="layaway_order",
        entity_id=order.id,
        detail=(
            f"{order.reference}; advance held {order.advance_amount}"
            + (f"; reason {reason.strip()}" if reason.strip() else "")
        ),
    )
    return order
