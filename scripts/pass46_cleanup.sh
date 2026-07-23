#!/usr/bin/env bash
# Pass 46 — repo-städning. Körs EN gång på en granska-gren, från repo-roten.
# Använder git mv/git rm så historiken bevaras. Kör sedan: packa upp
# pass46-överlägget (uppdaterade filer), git add -A, commit.
set -euo pipefail
[ -d .git ] || { echo "Kör från repo-roten (ingen .git hittad)"; exit 1; }

mkdir -p docs/verification docs/history docs/10_Passes scripts/demos

# 1) Regenererbara körartefakter i roten: bort (skrivs av tjänsterna per projekt)
git rm -q -f crow-*.json estimate-structure.json 2>/dev/null || true
git rm -q -f demo-result.json 2>/dev/null || true

# 2) Demoskript
for f in B*_DEMO.py; do [ -e "$f" ] && git mv "$f" scripts/demos/; done

# 3) Verifikationsbevis och release-JSON -> docs/verification/
for f in B*_VERIFICATION.json B8_*_RULES.json B8_3_PROFILE.json \
         PASS*_VERIFICATION.json SPRINT4_VERIFICATION.json D1_VERIFICATION.json \
         CAD_TEXT_*.json CCM_*.json GEOMETRY_FRAMEWORK_*.json RELEASE*.json \
         V0_7_0A1_*.json WORKBENCH_BETA.json GRAPH_*_VERIFICATION.json \
         IFC_RELATIONS_*.json INFERENCE_*_VERIFICATION.json; do
  [ -e "$f" ] && git mv "$f" docs/verification/
done

# 4) Ersatta changelogs och releasedokument -> docs/history/
for f in CHANGELOG_*.md CROW_VENT_*.md BUILDING_GRAPH_RC1*.md \
         REASONING_ENGINE_*.md VENT_INTELLIGENCE_*.md; do
  [ -e "$f" ] && git mv "$f" docs/history/
done

# 5) docs: vik in 40_Architecture i 00_Architecture, samla pass-dokument
if [ -d docs/40_Architecture ]; then
  git mv docs/40_Architecture/* docs/00_Architecture/
  rmdir docs/40_Architecture
fi
for f in docs/SPRINT_*.md docs/PASS_*.md docs/RC_READINESS_*.md \
         docs/INFERENCE_ENGINE_RC1_SPRINT*.md; do
  [ -e "$f" ] && git mv "$f" docs/10_Passes/
done

echo "Klart. Packa nu upp pass46-överlägget, kör 'git add -A' och granska diffen."
