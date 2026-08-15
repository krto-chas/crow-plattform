# Pass 45 — Kalkylvy i Workbench (frontend för testning)

## Vad
Ny vy "Kalkyl" (Σ i railen) i den befintliga Workbench-frontenden, byggd i
samma designspråk (paneler, eyebrows, metric-grid, chips). Den kör hela
Pass 41–44-kedjan interaktivt:

- **Källor:** kryssbara DXF-tillgångar ur projektet (geometri-takeoff via
  befintlig vent-pipeline), mängdförteckning som rader
  (`beteckning;mängd;enhet`), beskrivningstext, och prisbok som JSON med
  "Ladda prisboksmall"-knapp.
- **Resultat:** totaler (material/arbete/timmar/SEK), avstämda rader med
  statusbadge (corroborated grön, discrepant bärnsten, unit_mismatch röd)
  och per-källa-mängder, beställarfrågor, opris-satta rader med skäl, samt
  CSV-export av kalkylen (Excel-vänlig med BOM och semikolon).

## Backend
`POST /api/projects/{project_id}/takeoff` — tar geometry_checksums,
table_rows, text_segments, price_book, length_tolerance; kör extraktorer →
konsolidering → prissättning; 422 om ingen källa anges. Återanvänder
`get_vent_model` för geometrin och injicerar ventlexikonet på appnivå
(appskalet får komponera domänmoduler; backbone-kontrakten rör inte vent).

## Testa så här
```bash
pip install -e ".[dev]" && python -m crow_workbench
# öppna http://127.0.0.1:8000 → skapa projekt → importera DXF →
# Σ Kalkyl → kryssa ritningen, klistra mängdförteckning,
# Ladda prisboksmall → Kör kalkyl
```
Utan projekt fungerar tabell+text+prisbok direkt (ad hoc-läge).

## Verifiering
2 nya API-tester (konsolidering+prissättning via HTTP, källkrav 422).
Totalt 420 gröna, mypy strict 204 filer, ruff 0. Frontend-serveringen
verifierad via TestClient (vyn, railknappen och skriptet levereras).
