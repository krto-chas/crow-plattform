# Överlämning mellan Codex och Claude Code

GitHub Issue och PR är gemensam källa till uppdrag och resultat. En uppgift,
en ansvarig implementerare, en branch och en separat worktree. Använd aldrig
samma arbetskatalog samtidigt. Samordna ändringar i gemensamma kontrakt,
migreringar och ADR:er innan parallell implementation.

## Arbetsflöde

1. Product owner prioriterar och utser implementerare.
2. Implementeraren hämtar main, planerar, bygger, committar och kör verifier
   samt reviewer enligt DEVELOPMENT.md.
3. Vid överlämning granskar den andra modellfamiljen samma SHA i en separat
   arbetskatalog. Den får inte ändra implementerarens branch.
4. Fynd dokumenteras i PR eller Issue. Implementeraren korrigerar och
   uppdaterar revision och rapporter. Tidigare resultat blir inaktuella.
5. GitHub CI måste vara grön för aktuell PR. Product owner godkänner merge.

Ömsesidig granskning krävs när product owner begär det eller vid ändringar
i auth, kundisolering, filhantering eller intyg. Om andra verktyget inte
är tillgängligt: rapportera EJ GRANSKAT och invänta beslut; påstå inte att
oberoende granskning har skett. För små ändringar kan product owner avstå
från granskning mellan modellfamiljer; lokala grindar och CI kvarstår.

## Överlämningsmall (PR-beskrivning eller Issue)

```yaml
task: <issue>
repository: crow-plattform
branch: <branch>
implemented_by: <codex eller claude>
review_requested_from: <claude eller codex>
base_sha: <full SHA>
head_sha: <full SHA>
scope: []
acceptance_criteria: []
relevant_adrs: []
local_verification: EJ VERIFIERAT
review_status: EJ GRANSKAT
github_ci: PENDING
review_focus: []
known_limitations: []
```

Bifoga faktiska kommandon, exitkoder, testresultat och fynd med fil/rad.
Inga hemligheter eller kunddata i överlämningen. Status är aldrig bevis i
sig. Kontrollera revisionen före och efter varje körning.

Detta protokoll startar inte externa agenter automatiskt. Product owner
eller lead lämnar över via GitHub och startar det andra verktyget.
