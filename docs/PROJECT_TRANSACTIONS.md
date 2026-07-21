# Project Transaction Boundary

En projektkörning producerar flera artefakter:

- uppdaterat `CrowProject`,
- `ProjectRun`,
- en eller flera Decision Graphs.

Dessa ska sparas atomärt. `ProjectUnitOfWork` definierar transaktionsgränsen:

```text
begin
  ├── save project
  ├── save graph 1
  ├── save graph N
  └── commit
```

Vid fel sker rollback och inga delresultat får bli synliga.

`InMemoryProjectUnitOfWork` är referensimplementation och testdubbel. Databas- och
filbaserade implementationer ska följa samma kontrakt.
