# CAF-TPL-003 Architecture Review Checklist

Used before tagging a release. Rows marked (auto) are enforced mechanically by `crow review` / CI; the rest are human judgement.

| # | Check | How |
|---|---|---|
| 1 | Required architecture documents exist | (auto) ARC-001 |
| 2 | Foundational decisions recorded as ADRs | (auto) ARC-002 |
| 3 | CI workflow exists and is green | (auto) ARC-003 + CI status |
| 4 | Release documented in CHANGELOG | (auto) ARC-004 |
| 5 | Dependency direction respected: SDK/conformance import no pipeline or module packages | grep imports; ADR-003 |
| 6 | Public contract changes match the version line (no breaking change inside a frozen line) | diff public API vs previous release |
| 7 | New capabilities have provenance and audit coverage | review new models for provenance fields and event emission |
| 8 | Documentation updated where behaviour changed; no duplication introduced | CAF-002 §7 |
| 9 | Security-relevant changes mapped to ADR-011 (implemented vs target) | review |
| 10 | Verification manifest complete and all quality gates `pass` | CAF-REL-001 |
