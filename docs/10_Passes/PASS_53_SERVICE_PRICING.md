# Pass 53 — Serviceprissättning för provtryckning

## Syfte
Från mängder till kronor: en prisbokdriven offertmotor för provtryckning som
konsumerar risermodellens service-payload och ger ett deterministiskt
offertunderlag med Decimal-pengar (ADR-0009).

## Byggt — `crow_pressure_test.pricing`
- `ServicePriceBook`/`ServicePriceEntry` — à-priser per servicekod;
  `default_service_price_book()` kalibrerad mot Berghällen-anbudet
  (sträng 675, låda 1500, gjutetapp 1600, timme 925, etablering 3000,
  slutrapport 1500) men fullt utbytbar per projekt.
- `price_pressure_test_offer` — strängar per trapphus + manuella poster
  (`OfferItemRequest`) + etableringar → offertpayload
  `crow-pressure-test-offer-v0.1`. Poster utan prisbokspost blir
  reservationer, aldrig tyst nollade. Fast pris = summa × (1 + risk),
  avrundat till närmaste tusenlapp.

## Grindar
Ruff 0, mypy strict 0, 6 nya prissättningstester gröna.
