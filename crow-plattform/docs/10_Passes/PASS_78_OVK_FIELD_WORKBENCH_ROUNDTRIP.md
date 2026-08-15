# Pass 78 — OVK Field → Workbench Roundtrip

## Scope

Göra serverlagrad fältdata synlig och verifierbar i OVK Workbench utan att automatiskt omvandla observationer, findings eller fotografisk evidens till normativa kontrollbeslut.

## Fältkontext

Fältsynken skickar separat kontext för `inspection_id`:

- `project_id`
- `inspector`

Kontexten lagras separat från den validerade `FieldInspectionData`-snapshoten så att domänmodellen inte utökas med UI-/sessionsdata.

## Workbench projection

`GET /api/ovk/field/workbench/{inspection_id}` projicerar den senaste serversnapshoten till en read-only Workbench-vy med:

- lägenheter/lokaler,
- rum,
- findings,
- feltyp och allvarlighetsgrad,
- system-ID,
- regelreferenser,
- fotometadata,
- verifieringsstatus,
- `media_id`,
- `evidence_id`,
- URL till verifierade bildbytes.

Ett foto visas som verifierat endast när ett serverkvitto finns och dess SHA-256 överensstämmer med fotometadatan i snapshoten.

## Normativ gräns

Passet skriver inte automatiskt fält-findings till kontrollpunkter, slutsats eller protokollstatus. Fältevidensen är underlag för Workbench och mänsklig review.

## TODO — fältenhetens retention och restore

Besluta hur länge en färdig/synkad besiktning ska ligga kvar lokalt på en fältenhet.

Överväg en explicit retention-policy, exempelvis tidsbaserad rensning, manuell arkivering eller rensning först efter verifierad serversynk. Beslutet ska ta hänsyn till offlinearbete, lagringsutrymme, känslig objektsinformation och behov av felsökning/återbesök.

Utred även server → fältenhet restore. En tidigare synkad besiktning bör vid behov kunna hämtas tillbaka från servern till fältappen, inklusive domänsnapshot och verifierad media/evidence, i stället för att systemet är beroende av att IndexedDB-data sparas permanent på samma enhet.

Innan restore implementeras ska följande semantik beslutas:

- om restore skapar en read-only kopia eller ett redigerbart nytt lokalt utkast,
- hur versions-/konflikthantering sker om både server och enhet har ändringar,
- om verifierade serverbilder materialiseras lokalt eller hämtas on demand,
- när lokala blobbar får rensas efter serversynk,
- hur användaren ser vilken version som är auktoritativ.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build

Regressioner ska täcka fältkontext, projektion av rum/findings/regelreferenser, verifierad media/evidence och att en bild utan serverkvitto aldrig presenteras som verifierad.
