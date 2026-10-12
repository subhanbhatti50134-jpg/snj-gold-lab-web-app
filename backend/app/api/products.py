
from fastapi import APIRouter, Depends, HTTPException, status
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
from app.schemas.product import ProductCreate, ProductOut

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
):
    product = Product(**payload.model_dump())
    db.add(product)

    try:
        db.commit()
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists",
        )

    return product


@router.get(
    "",
    response_model=list[ProductOut],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def list_products(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    statement = select(Product).order_by(Product.id.desc())

    if not include_inactive:
        statement = statement.where(Product.active.is_(True))

    return db.scalars(statement).all()


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
