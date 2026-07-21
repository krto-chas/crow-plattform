# Decision Graph och Evidence Integrity

## Automatisk grafkoppling

`build_decision_graph` skapar noder och relationer för hela den vertikala beslutskedjan:

```text
Claim
→ Conflict
→ Authority Decision
→ Accepted Claim
→ Technical Delta
→ Commercial Impact
→ ÄTA Opportunity
→ Estimate Line / Question / Reservation
```

Evidence och regler blir separata grafnoder.

## Integritetsregler

Evidence Graph-valideringen säkerställer:

- unika Evidence-ID:n,
- att refererade Claims existerar,
- att statement inte är tomt,
- att regel-evidens har `rule_id`.

## Idempotens

En deterministisk fingerprint skapas från Claims, authority policy, kostnader,
kvantitet och avrundningspolicy. Samma fingerprint återanvänder samma resultat.

## Source invalidation

När en källa förändras kan alla beroende grafnoder identifieras genom
`invalidate_from_source`. Dessa objekt ska betraktas som inaktuella och räknas om.
