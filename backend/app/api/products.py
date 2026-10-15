

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import (
    MANAGE_ROLES,
    READ_ROLES,
    require_roles,
)
from app.db.session import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.services.audit import log_audit
from app.services.purge import purge_product

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    product = Product(**payload.model_dump())
    db.add(product)

    try:
        log_audit(
            db,
            username=user.username,
            action="product.create",
            entity_type="product",
            detail=f"{product.sku} ({product.name})",
        )
        db.commit()
        db.refresh(product)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists",
        ) from exc

    return product


@router.get(
    "",
    response_model=list[ProductOut],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def list_products(
    include_inactive: bool = False,
    search: str | None = Query(default=None, min_length=1, max_length=160),
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    statement = select(Product).order_by(Product.id.desc())

    if not include_inactive:
        statement = statement.where(Product.active.is_(True))

    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            Product.name.ilike(term) | Product.sku.ilike(term)
        )

    return db.scalars(statement.limit(limit)).all()


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(status_code=422, detail="No changes provided")

    for field, value in changes.items():
        setattr(product, field, value)

    try:
        log_audit(
            db,
            username=user.username,
            action="product.update",
            entity_type="product",
            entity_id=product.id,
            detail=", ".join(sorted(changes)),
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists",
        ) from exc

    db.refresh(product)
    return product


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_200_OK,
)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    """Permanently delete a product that has no history yet."""
    detail = purge_product(db, product_id, username=user.username)
    return {"deleted": True, "detail": detail}
