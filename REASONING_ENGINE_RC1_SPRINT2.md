# Crow Platform 2.3 – Reasoning Engine RC1 Sprint 2

## Omfattning

Sprinten lägger en generell och domänneutral regelmotor ovanpå Building Graph och Traversal Engine.

## Levererat

- datadrivna och versionssatta JSON-regler
- objektselektorer för typ, disciplin och metadata
- krav på relationer, egenskaper och evidens
- operatorerna `exists`, `missing`, `equals`, `not_equals` och `in`
- deterministiska findings-ID:n
- severity: `info`, `warning`, `error`, `critical`
- confidence, rekommendation och evidenskedja per finding
- standardregelpaketet `crow.core.quality`
- validerings- och utvärderings-API

## API

```text
GET  /api/projects/{project_id}/reasoning/rules
POST /api/projects/{project_id}/reasoning/rules/validate
GET  /api/projects/{project_id}/reasoning/findings
POST /api/projects/{project_id}/reasoning/evaluate
```

## Verifiering

- 264 tester godkända
- Python compileall godkänd
- ZIP-integritet verifierad
