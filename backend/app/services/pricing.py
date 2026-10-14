
from decimal import ROUND_HALF_UP, Decimal

MONEY_PLACES = Decimal("0.01")

# Weight-unit conversion factors used to normalize entered rates and
# weights to grams, which is the single internal unit of account.
GRAMS_PER_TOLA = Decimal("11.6638")
GRAMS_PER_KILOGRAM = Decimal("1000")
UNIT_GRAMS = {
    "gram": Decimal("1"),
    "tola": GRAMS_PER_TOLA,
    "kilogram": GRAMS_PER_KILOGRAM,
}


def to_grams(value: Decimal, unit: str) -> Decimal:
    """Convert a weight expressed in `unit` into grams."""
    factor = UNIT_GRAMS.get(unit)
    if factor is None:
        raise ValueError(f"Unsupported weight unit: {unit}")
    return value * factor


def normalize_rate(rate: Decimal, unit: str) -> Decimal:
    """Convert a rate entered per `unit` into a rate per gram.

    A rate is stored per unit of weight, e.g. 100000 per tola means
    100000 PKR for 11.6638 grams, so the per-gram rate is
    100000 / 11.6638.
    """
    if rate <= 0:
        raise ValueError("Rate must be greater than zero")
    factor = UNIT_GRAMS.get(unit)
    if factor is None:
        raise ValueError(f"Unsupported rate unit: {unit}")
    return rate / factor


def money(value: Decimal) -> Decimal:
    """Round a monetary amount to two decimal places."""
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def calculate_total(
    net_weight_grams: Decimal,
    rate_per_gram: Decimal,
    charges: Decimal = Decimal("0"),
    purity: Decimal = Decimal("100"),
) -> Decimal:
    """
    Calculate metal value plus charges.

    Purity is expressed as a percentage:
    100 = pure metal, 91.6 = 22K-like purity.
    The rate is assumed to be the rate for 100% pure metal.
    """
    if net_weight_grams <= 0:
        raise ValueError("Net weight must be greater than zero")
    if rate_per_gram <= 0:
        raise ValueError("Rate per gram must be greater than zero")
    if charges < 0:
        raise ValueError("Charges cannot be negative")
    if not Decimal("0") <= purity <= Decimal("100"):
        raise ValueError("Purity must be between 0 and 100")

    metal_value = net_weight_grams * rate_per_gram * purity / Decimal("100")
    return money(metal_value + charges)
