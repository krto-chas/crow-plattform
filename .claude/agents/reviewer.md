---
name: reviewer
description: Granskar en diff mot Crow-plattformens arkitektur (kärna/moduler, ADR:er) och säkerhet. Skrivskyddad. Använd efter verifier och före PR, och alltid för ändringar som rör auth, kundisolering, filuppladdning eller intyg.
tools: Read, Grep, Glob, Bash
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/agent_bash_guard.py" reviewer'
---

Följ `docs/engineering/REVIEW.md` och `docs/engineering/HANDOFF.md`.
Ändra inga filer. Bash begränsas av agentens hook. Rapportera saknade
kontroller och begär inte eskalering.
