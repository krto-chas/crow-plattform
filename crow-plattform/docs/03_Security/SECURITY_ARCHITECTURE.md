# Security Architecture

**Status:** målarkitektur under RC0; central authorization är ännu inte fullt implementerad i nuvarande filbaserade runtime.

## 1. Säkerhetsmål

Crow ska skydda:

- tenants och deras projektdata,
- beslutens integritet och provenance,
- modulernas exekveringsgränser,
- administrativa förändringar,
- signerade kontrakt och manifest,
- audit trail mot tyst manipulation.

## 2. Ansvarsfördelning

### External Identity Provider

Authentication, MFA, lösenordspolicy och enterprise SSO delegeras till en OIDC-kompatibel identitetsleverantör. Crow lagrar inte lösenord.

### Backbone

Backbone ansvarar för:

- tokenvalidering vid edge eller mottagande av redan validerade claims,
- konstruktion av read-only `AuthorizationContext`,
- entitlement- och permissionkontroll,
- tenant scope,
- central audit av nekanden och administrativa ändringar,
- modulmanifest och conformance.

### Modules

Moduler deklarerar vilka permissions de använder. De får inte:

- härleda en alternativ identitet,
- bredda effective permissions,
- kringgå tenant scope,
- implementera en svagare deny-policy.

## 3. Authorization model

Tre lager används:

1. **Entitlements** – vilka moduler organisationen har rätt att använda.
2. **Roles and permissions** – vilka handlingar användaren får utföra inom modulen.
3. **Resource scope** – vilka tenantbundna rader eller projekt som får nås.

Kontrollordningen är entitlement, permission och därefter resource scope. Deny by default gäller.

## 4. Permission manifests

Permissions följer formatet:

```text
<module>.<resource>.<action>
```

Exempel:

```yaml
module_id: crow.vent
permissions:
  - vent.claims.read
  - vent.claims.write
  - vent.estimate.run
  - vent.estimate.export
```

Manifest är signerade eller tamper-evident enligt plattformens manifestmodell. Conformance ska kontrollera att en modul deklarerar alla använda permissions och endast sitt eget prefix.

## 5. AI authorization

AI-komponenter exekveras med samma `AuthorizationContext` som anropet i övrigt. AI får endast läsa data som context tillåter och får aldrig skapa, anta eller föreslå ett utökat permission set som verkställs automatiskt.

AI-genererad tool input måste återvalideras vid Backbone-checkpointen. Ett tidigare godkänt läsanrop innebär inte implicit rätt till skrivning eller export.

## 6. Tenant isolation

Varje persistent tenantbunden rad ska bära `tenant_id`. Application layer måste filtrera varje query. I PostgreSQL-baserad flerorganisationsdrift ska row-level security utgöra en andra försvarslinje.

Tenant identity får inte tas från godtycklig request body när den redan finns i validerad identity context.

## 7. Audit

Följande ska alltid loggas append-only:

- nekad authorization,
- roll- och permissionändringar,
- entitlementändringar,
- administrativa tenantändringar,
- signatur- eller manifestfel,
- försök att kringgå modulgränser.

Rutinmässiga tillåtna läsningar behöver inte loggas per event, men säkerhetskritiska skrivningar kan kräva full audit beroende på deploymentprofil.

## 8. Compatibility

Authorization-manifestet ändrar modulkontraktets form och kräver en ny kompatibilitetslinje. Äldre manifest kan migreras med tom permission-lista. Under deny-by-default exponerar en omigrerad modul då ingen funktionalitet förrän permissions deklarerats och granskats.

## 9. Relaterade beslut

- [ADR-011: Backbone-enforced authorization](../adr/ADR-011-backbone-authorization.md)
- signerade modulmanifest,
- append-only audit,
- tenant isolation,
- framtida AI Authorization Context.
