from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload

GRAMS_PER_TOLA = Decimal("11.6638")


def test_rate_unit_tola_is_normalized_to_per_gram(client):
    entered = Decimal("116638")  # per tola

    response = client.post(
        "/api/rates",
        headers=login_headers(client, "manager"),
        json={
            "metal": "gold",
            "purity": 99.99,
            "rate_per_gram": float(entered),
            "unit": "tola",
            "source_note": "Market check",
            "verified_by": "Pytest",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["unit"] == "tola"
    assert Decimal(str(data["entered_rate"])) == entered
    # 116638 per tola / 11.6638 g per tola = 10000 per gram.
    assert Decimal(str(data["rate_per_gram"])) == Decimal("10000")


def test_rate_unit_kilogram_is_normalized(client):
    response = client.post(
        "/api/rates",
        headers=login_headers(client, "manager"),
        json={
            "metal": "silver",
            "purity": 99.99,
            "rate_per_gram": 250000,
            "unit": "kilogram",
            "verified_by": "Pytest",
        },
    )
    assert response.status_code == 201, response.text
    assert Decimal(str(response.json()["rate_per_gram"])) == Decimal("250")


def test_transaction_uses_normalized_rate_for_total(client):
    # Rate: 116638 per tola == 10000 per gram.
    client.post(
        "/api/rates",
        headers=login_headers(client, "manager"),
        json={
            "metal": "gold",
            "purity": 100,
            "rate_per_gram": 116638,
            "unit": "tola",
            "verified_by": "Pytest",
        },
    )

    product = create_product(client)

    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=transaction_payload(
            product["id"], weight=2, rate=None, amount_paid=0
        ),
    )
    assert response.status_code == 201, response.text

    # The active tola rate is picked up and normalized automatically:
    # 2g * 10000/g = 20000.
    assert Decimal(str(response.json()["total_amount"])) == Decimal("20000.00")
    assert Decimal(str(response.json()["rate_per_gram"])) == Decimal("10000")


def test_transaction_rate_override_in_tola(client):
    product = create_product(client)

    payload = transaction_payload(product["id"], weight=2, rate=100)
    payload["rate_per_gram"] = 116638
    payload["rate_unit"] = "tola"

    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    # Override of 116638/tola = 10000/g; 2g -> 20000.
    assert Decimal(str(response.json()["total_amount"])) == Decimal("20000.00")


def test_invalid_rate_unit_is_rejected(client):
    response = client.post(
        "/api/rates",
        headers=login_headers(client, "manager"),
        json={
            "metal": "gold",
            "purity": 100,
            "rate_per_gram": 100,
            "unit": "ounce",
            "verified_by": "Pytest",
        },
    )
    assert response.status_code == 422
