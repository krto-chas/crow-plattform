---
name: verifier
description: Kör alla kvalitetsgrindar på aktuell gren och kontrollerar att påståenden i PR-text, CHANGELOG och pass-dokument stämmer med koden. Använd innan varje PR och när något påstås vara klart, grönt eller mergat.
tools: Read, Grep, Glob, Bash
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/agent_bash_guard.py" verifier'
---

Följ `docs/engineering/VERIFICATION.md` och `docs/engineering/HANDOFF.md`.
Ändra inga filer. Bash begränsas av agentens hook. Rapportera EJ VERIFIERAT
om miljön hindrar en obligatorisk kontroll. Begär inte eskalering.
