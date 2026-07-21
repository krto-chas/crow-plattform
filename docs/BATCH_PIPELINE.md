# Batch Pipeline

`run_batch_claim_to_estimate` behandlar flera fristående konflikter i samma projekt.

Varje konflikt identifieras med:

```text
(namespace, subject, property)
```

Prissättningsindata tillhandahålls per conflict key. Konflikter utan prissättningsindata
lämnas obehandlade i detta kommersiella flöde och kan hanteras separat eller skickas till
Human Review.

Batchresultatet innehåller:

- sorterade konfliktresultat,
- Claims som inte ingick i ett prissatt konfliktflöde.
