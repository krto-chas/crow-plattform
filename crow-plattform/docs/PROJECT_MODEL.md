# Crow Project Model v1.0

`CrowProject` är den sammanhållande aggregatroten för ett analys- och kalkylprojekt.

## Projektet äger

- dokumentregister,
- Claims,
- authority policy,
- aktiverade moduler,
- körhistorik,
- projektstatus.

## Tillstånd

```text
Draft
→ Ready
→ Processing
→ Completed
       ↘
        Review Required
```

Ett projekt kan endast markeras `Ready` när det har:

- minst ett aktivt dokument,
- minst ett Claim,
- en authority policy,
- minst en aktiverad modul.

## Dokumentdisciplin

Claims får endast läggas till om deras proveniens refererar till ett aktivt dokument i
projektet. Detta förhindrar frikopplade fakta utan dokumentkontext.

## Körning

`execute` genomför batchflödet, bygger en Decision Graph per konflikt och sparar ett
`ProjectRun`. En olöst authority decision sätter projektet till `Review Required`.

## Persistens

`JsonProjectRepository` är referensimplementation för projektets stabila kärndata.
Körresultat och grafer sparas genom sina separata persistenskontrakt.
