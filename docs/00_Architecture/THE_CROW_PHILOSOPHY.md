# The Crow Philosophy

## Människan äger beslutet

Crow försöker inte ersätta yrkeskunskap eller ansvar. Plattformen ska göra det möjligt för en människa att förstå vad som observerades, vad som tolkades, vilken regel som användes och varför ett beslut accepterades.

Ett system kan automatisera beräkningar. Det kan inte automatisera bort ansvar.

## Observation är inte tolkning

Det som står i en handling och det som en tekniker drar för slutsats är två olika saker. Crow bevarar denna skillnad.

En observation ska beskriva det som kan avläsas. Ett claim ska beskriva den tolkning som föreslås. Ett accepterat claim ska visa varför tolkningen får användas vidare.

## Osäkerhet ska vara synlig

Ett obesvarat problem är bättre än ett säkert formulerat fel. När underlaget är motsägelsefullt eller otillräckligt ska Crow kunna stoppa flödet och kräva review.

Human review är inte ett misslyckande i automationen. Det är en avsiktlig säkerhetsmekanism.

## Proveniens är en del av sanningen

Ett påstående utan källa är svagare än ett påstående med identifierbar källa. Ett beslut utan förklarad regel är svagare än ett beslut med versionsbunden regel.

Crow behandlar därför provenance som domändata, inte som loggtext.

## Determinism skapar förtroende

När ekonomi, omfattning eller tekniska slutsatser påverkas måste resultatet kunna reproduceras. Samma verifierade underlag och samma regler ska ge samma resultat.

Sannolikhetsbaserade komponenter kan bidra med kandidater, men de deterministiska gränserna ska vara tydliga.

## AI är rådgivare, inte auktoritet

AI kan hitta, extrahera, klassificera och formulera. AI kan föreslå samband som en människa annars hade missat. Men AI:s svar är inte självbärande evidens.

AI får aldrig:

- ersätta originalkällan,
- avgöra rättslig eller kontraktuell authority utan policy,
- tyst ändra ett ekonomiskt resultat,
- utöka en identitet eller tenants behörigheter,
- dölja att ett resultat är probabilistiskt.

## Säkerhet är inte en moduldetalj

Authorization, audit och tenant isolation är plattformsansvar. En modul ska inte kunna välja en svagare säkerhetsmodell än resten av systemet.

Moduler deklarerar vad de behöver. Backbone avgör vad som tillåts.

## Kunskap ska överleva individen

I många verksamheter finns avgörande kunskap i e-posttrådar, minnen och lokala kalkylblad. Crow ska bevara beslutets väg så att en annan person kan förstå det långt senare.

Det innebär att ett resultat inte bara ska kunna öppnas. Det ska kunna granskas.

## En kostnad är en konsekvens, inte en startpunkt

Crow börjar inte med priset. Plattformen börjar med underlaget och följer påverkan genom tekniskt beslut, delta, scope och kommersiell bedömning.

Ekonomin blir därmed slutet på en spårbar kedja, inte ett isolerat tal.

## Plattform före domän

Ventilation är en viktig första domän, men den ska inte definiera plattformens gränser. Samma arkitekturella principer ska kunna användas inom bygg, energi, compliance, risk och andra kunskapsintensiva områden.

Crow Platform bevarar kärnkontrakten. Crow Applications uttrycker domänens språk.

## Den vägledande frågan

När en ny funktion föreslås ska projektet fråga:

> Gör detta beslutet mer spårbart, reproducerbart, förklarbart eller säkert?

Om svaret är nej behöver funktionen motiveras på annat sätt eller placeras utanför kärnan.
