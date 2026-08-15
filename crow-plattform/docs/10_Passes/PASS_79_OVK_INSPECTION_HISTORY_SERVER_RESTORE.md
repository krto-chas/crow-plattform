# Pass 79 — OVK Inspection History + Server Restore

## Scope

Göra servern till långsiktig sanningskälla för OVK-fältbesiktningar och möjliggöra att en ny besiktning skapas med struktur och historik från en tidigare serverlagrad besiktning utan att äldre observationer eller fotografisk evidens presenteras som nya observationer.

## Principer

- En avslutad/synkad besiktning är historik och ska inte återanvändas genom att samma `inspection_id` skrivs över som en ny besiktning.
- En ny besiktning får bära `previous_inspection_id` och därmed ingå i en versionskedja.
- Servern är långsiktig lagringsplats. Fältenheten är arbetscache.
- Restore till fältenhet skapar ett **nytt lokalt utkast** med nytt `inspection_id`.
- Fastighets-/fältstruktur får återanvändas: lägenheter/lokaler och rum materialiseras med nya lokala ID:n.
- Tidigare findings, bilder och evidence-ID:n följer med endast som **historiska referenser**. De blir inte nya `FieldFinding` eller `OvkPhotoEvidence`.
- Ett kvarstående fel måste registreras som en ny observation och får då peka tillbaka på den tidigare observationen.

## API-kontrakt

- `GET /api/ovk/field/history?project_id=...` listar serverlagrade fältbesiktningar för projektet.
- `GET /api/ovk/field/history/{inspection_id}` returnerar en restore-projektion med struktur, historiska findings och verifierade mediareferenser.
- Fältkontexten får bära `previous_inspection_id` för nya besiktningar.

## Fältflöde

Fältappen kan välja en tidigare besiktning från servern och skapa ett nytt utkast:

1. välj projekt,
2. välj tidigare OVK,
3. ange nytt besiktnings-ID och besiktningsman,
4. materialisera lägenheter/lokaler + rum till nya lokala ID:n,
5. visa tidigare findings som read-only historik,
6. fortsätt den nya besiktningen offline på vanligt sätt.

## Konfliktgräns

Restore får inte skriva över ett lokalt utkast med samma nya `inspection_id`. Om ett utkast redan finns ska klienten stoppa och kräva ett uttryckligt senare konfliktbeslut. Pass 79 inför inte automatisk merge mellan två redigerade versioner.

## TODO — lokal retention

Fastställ senare en explicit retentionpolicy för synkade fältutkast och mediablobbar. Servern är permanent/central historikkälla enligt vald organisationspolicy; fältenheten ska kunna rensa verifierat synkade arbetskopior efter beslutad tid utan att återbesiktningsförmågan går förlorad.

## TODO — ventilationstopologi och framtida injustering

Bygg vidare på fältmodellens stabila lägenhets-/lokalstruktur med en framtida `MeasurementPoint` som primär fysisk mätpunkt. Varje mätpunkt ska kunna kopplas till en valfri stamrelation:

- `unassigned` — ingen stam bestämd,
- `inferred` — Crow föreslår/sammanställer en sannolik stam,
- `confirmed` — besiktningsmannen har bekräftat stamkopplingen.

En lägenhet kan ha flera mätpunkter på olika stammar och flera mätpunkter i samma lägenhet kan dela stam. Stamkopplingen ska kunna anges under besiktningen eller efteråt och ärvas som historisk struktur till nästa besiktning.

Detta ska senare möjliggöra:

- mönsteranalys av avvikande flöden längs samma stam,
- sannolikhetsvarning om stamrelaterade problem,
- ett successivt uppbyggt flödesschema/systemträd för fastigheten,
- korsning med Vent-modulens projekterade kanal-/systemtopologi,
- framtida Injusteringsmodul där känd topologi, projekterade flöden och uppmätta flöden kan användas som underlag för **preliminära** beräkningar av donens förinställningar. Sådana beräkningar ska vara beslutstöd och inte ersätta faktisk injustering/mätverifiering.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build
