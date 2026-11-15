# Crow Plattform – arbetsregler för Claude Code

Du är lead i det här repot: du planerar, implementerar och samordnar. Stoffe är
product owner och den enda som godkänner merge till `main`.

## Arkitektur (bryts aldrig utan ADR)

- Kärnan (`src/`) är grunden. Moduler (`modules/*`) ligger ovanpå och bär
  sakkunskapen. Kärnan importerar aldrig en modul; beroenden går via protokoll
  och entry points (`crow.modules`).
- Byggnadsgrafen i kärnan är den gemensamma byggnadsmodellen
  (`docs/adr/ADR-012-building-graph-as-shared-model.md`). Fastighet och graf
  ligger på kundnivå; projekt refererar till dem.
- Backend är Python. Persistens går mot PostgreSQL via SQLAlchemy/Alembic,
  införd stegvis.
- Beslut finns i `docs/adr/`, grundregler i `docs/CONSTITUTION.md` och
  `docs/MODULE_CONTRACT.md`. Läs relevant ADR innan du ändrar något den täcker.
  Behövs ett avsteg: skriv ett ADR-förslag och fråga, ändra inte tyst.
- OVK 1.0 får inte tappa fart: rör inte dess release-grindar för annat arbete.

## Arbetssätt

1. **Planera kort** innan du skriver kod: vad ändras, i vilka filer, vilken
   ADR berörs. Är uppgiften tvetydig, fråga i stället för att välja den större
   tolkningen.
2. **Små diffar.** Rör bara det uppgiften kräver. Sådant du upptäcker vid sidan
   om listas som uppföljning i PR:en, det fixas inte i samma ändring.
3. **Tester följer med** varje beteendeändring. Kundfiler hålls utanför repot;
   endast checksummor checkas in.
4. **Arbeta på gren**, aldrig direkt på `main`. En uppgift, en PR.
5. Docstrings och kommentarer på svenska.

## Innan PR

Kör subagenterna i den här ordningen och åtgärda det de hittar:

1. `verifier` – kör alla grindar och kontrollerar påståenden mot koden.
2. `reviewer` – granskar diffen mot arkitektur och säkerhet.

Skapa PR först när verifier rapporterar PASS och reviewer inte har några
blockerare. Lägg verifierns kommandoutfall i PR-beskrivningen. Skriv aldrig
"alla grindar gröna" eller ett testantal som du inte har sett i ett utfall
från den här grenen.

Extra säkerhetsgranskning krävs för ändringar som rör autentisering, sessioner,
kundisolering, filuppladdning/-konvertering eller intygens checksumma och
verifiering. Säg det uttryckligen till `reviewer` när du anropar den.

## Grindar (samma som `.github/workflows/ci.yml`)

```bash
ruff format --check .
ruff check .
mypy
mypy --strict modules/*/src modules/*/tests
pytest -q
for m in modules/*; do [ -d "$m/tests" ] && pytest -q "$m/tests"; done
python -m crow_module_conformance.cli review --root .
```

CI är den slutliga kontrollen. Lokalt gröna grindar ersätter den inte.
