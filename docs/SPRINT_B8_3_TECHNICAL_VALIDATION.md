# Sprint B8.3 — Missing Information and Technical Validation

Version: `0.6.0-alpha.12`.

B8.3 introduces an explicit completeness gate over canonical Accepted Claims.

A validation profile defines technical information that must exist before later
decision or commercial-processing stages may rely on the project model.

## Issue types

- `missing_information`
- `invalid_value`
- `low_confidence`
- `ambiguous_match`

## Requirements

Each requirement contains one or more required claim roles. A role can constrain:

- subject or subject regular expression;
- predicate;
- unit;
- semantic-key content;
- minimum confidence;
- numeric validity;
- enumerated allowed values.

## Output

Crow emits `TechnicalValidationIssue` records with:

- stable fingerprint and ID;
- requirement and issue type;
- severity;
- missing role aliases;
- related Accepted Claim IDs;
- source document IDs;
- recommended action.

## CLI

Create a profile template:

```bash
crow technical template ./crow-technical-validation-profile.json
```

Run validation:

```bash
crow technical validate ./crow-project.json \
  --profile ./crow-technical-validation-profile.json
```

Optional Accepted Claims path:

```bash
crow technical validate ./crow-project.json \
  --profile ./crow-technical-validation-profile.json \
  --accepted ./crow-accepted-claims.json
```

Output:

```text
crow-technical-validation.json
```

Blocking issues are explicit gates. The validator does not invent missing
technical values and does not convert incomplete data into decisions.
