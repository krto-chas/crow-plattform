# Sprint B1 — Document Intake

Version `0.6.0-alpha.1`.

## User flow
```bash
crow project create ./demo --name "Demo"
crow project import ./demo/crow-project.json ./underlag --recursive
crow project show ./demo/crow-project.json
```

## Implemented
- domain-independent `CrowDocument` and `DocumentIndex`
- SHA-256 and metadata fingerprinting
- PDF page count
- filename metadata: document number, revision, discipline
- rule-based classification and roles
- exact duplicate detection
- revision chain with `SUPERSEDED`
- persistent JSON index
- CLI create/import/show

## Not included
No OCR, LLM, text extraction, symbol interpretation or region analysis.
The document graph model exists; automatic relation extraction comes later.
