# Decision Pipeline v1.0

Sprint A:s första kompletta vertikala beslutskedja:

```text
Claim
→ Conflict
→ Authority Decision
→ Accepted Claim
→ Technical Delta
→ Commercial Impact
→ ÄTA Opportunity
→ Estimate Line / Client Question / Reservation
```

## Säkerhets- och kvalitetsregler

- Obekräftad dokumentordning ger alltid Human Review.
- Ogiltiga auktoritetsgrafer stoppas.
- Tekniska och ekonomiska differenser använder `Decimal`.
- Avrundning sker genom explicit `RoundingPolicy`.
- Exportobjekt länkar tillbaka till den kommersiella möjligheten.
- Förklaringar genereras från strukturerad Evidence.
