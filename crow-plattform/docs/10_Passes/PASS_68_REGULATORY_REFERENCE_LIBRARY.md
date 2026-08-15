# Pass 68 – Regulatory Reference Library

## Syfte

Skapa ett versionsmedvetet referensbibliotek för OVK, ventilation och närliggande
arbetsmiljöregler. Biblioteket ska göra det möjligt för framtida findings,
kontrollpunkter och protokoll att hänvisa till stabila `source_id` och
`reference_id` i stället för fritext.

## Scope

Passet innehåller metadata och hänvisningar till officiella källor. Det kopierar
inte externa vägledningstexter och ersätter inte kontroll mot aktuell officiell
författning.

Initialt ingår:

- PBL 2010:900, särskilt 8 kap. 25 §.
- PBF 2011:338, särskilt 5 kap. 1–7 §§ och 18 §.
- BFS 2011:16 (OVK), med ändringskedja till och med BFS 2025:6.
- BFS 2012:7 (OVKAR).
- Boverkets nya regler BFS 2024:8 för hygien, hälsa och miljö.
- BBR BFS 2011:6 som historiskt referensverk efter 30 juni 2026.
- AFS 2023:12, 2023:10, 2023:14, 2023:3 och 2023:11.
- AFS 2020:1 som historisk föregångare till AFS 2023:12.

## Design

`crow_regulations` är installationsdata med frozen dataclasses och JSON-register.
Varje källa bär status, giltighetsperiod, officiell URL, ändrings-/ersättningsrelationer,
ämnestaggar och valfria punktreferenser.

Allmänna råd markeras som `guidance`, inte som bindande regel. Historiska regler
kan sökas separat och filtreras på datum.

## Evidensregel

Numeriska krav eller juridiska slutsatser får inte skapas enbart från registermetadata.
Den modul som använder en referens måste fortfarande visa vilken regelversion och
vilket underlag som ligger bakom bedömningen.

## Verifieringsdatum

Källregistret kontrollerades mot officiella källor 2026-08-09.
