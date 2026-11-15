# Crow Plattform – Codex

Du är lead när du implementerar. Följ docs/engineering/DEVELOPMENT.md,
REVIEW.md, VERIFICATION.md och HANDOFF.md. Läs relevanta ADR:er,
docs/CONSTITUTION.md och docs/MODULE_CONTRACT.md.

Använd projektets reviewer och verifier som separata subagenter innan PR.
Ge dem uppgift, acceptanskriterier, bas-SHA och HEAD-SHA. Om subagenter inte
är tillgängliga, rapportera detta; simulera inte oberoende granskning.
Verifier kör först, reviewer därefter. Efter korrigering körs båda om.
Använd read-only sandbox för granskning och verifiering; saknade
behörigheter eller beroenden rapporteras som EJ VERIFIERAT. Be inte om
eskalering för att kringgå en specialists begränsning.

Vid överlämning från Claude: följ HANDOFF.md, granska exakt revision och
ändra inte implementerarens branch. Ingen merge eller driftsättning utan
product owners beslut.
