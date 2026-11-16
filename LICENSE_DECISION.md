# License decision — SNJ Gold Lab

This repository (gold/silver/jewellery inventory & point-of-sale system) does
**not** yet carry an open-source license. Until a license is added, all rights
are reserved by default.

## Context

SNJ Gold Lab is **business software** that handles money, inventory, customer
and supplier ledgers, and audit logs. The license choice should reflect:

- **Commercial intent**: do you want others to be able to use, modify, and
  resell this system, or do you want to reserve commercial rights for yourself?
- **Liability**: financial/inventory software can cause real losses if it
  miscalculates. A strong warranty disclaimer and limitation of liability are
  essential.
- **Copyleft vs permissive**: a permissive license (MIT/Apache-2.0) maximizes
  adoption; a copyleft license (AGPL) requires hosted instances to share
  source, which can deter commercial hosting without a separate agreement.

## Recommended options

### Option A — Proprietary / "All Rights Reserved" (current state)
- You keep full control; no one may legally reuse or distribute the system.
- Appropriate if you plan to sell licenses or host it as a service yourself.
- No `LICENSE` file; add this `LICENSE_DECISION.md` as the record.

### Option B — MIT License (permissive)
- Allows use, modification, and commercial redistribution, including in
  closed-source products.
- Minimal obligations; strong warranty/liability disclaimer.
- Best if you want maximum adoption and don't mind others building on it.

### Option C — Apache-2.0 (permissive + patent grant)
- Like MIT with an explicit contributor patent grant and clearer contribution
  framework.
- Good if you want permissive reuse with added patent clarity.

### Option D — AGPL-3.0 (network copyleft)
- Anyone who offers the system as a hosted service must release their changes
  under AGPL too.
- Discourages closed-source commercial hosting without a separate commercial
  license from you.

## Recommendation

Because this is a **money-handling business system**, start with **Option A
(proprietary)** unless you specifically want to open-source it. If you do
choose to open-source it, **MIT or Apache-2.0** is the better fit over AGPL
(for a business tool you may want to monetize via hosting/support).

## How to adopt (if choosing an open-source license)

1. Pick a license (MIT or Apache-2.0 recommended).
2. Add a `LICENSE` file at the repository root with the official license text.
3. Add copyright: `Copyright (c) 2026 Muhammad Subhan`.
4. Keep this `LICENSE_DECISION.md` as the decision record.

> Do not treat SNJ Gold Lab as open-source licensed until a `LICENSE` file is
> present.
