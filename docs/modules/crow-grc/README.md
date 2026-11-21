# CROW GRC – Governance, Risk & Compliance

**Status:** planerad fristående modul, arkitekturförslag  
**Senast uppdaterad:** 2026-11-21  
**Föreslaget modul-ID:** `crow.grc`  
**Beslutsfattare:** produktägaren

CROW GRC ska vara en fristående verksamhetsmodul för styrning, riskhantering, kontrolluppföljning, incidenter och revisionsbar evidens. Den ska stödja både CROW:s egen styrning och kunders GRC-arbete, utan att dessa datamängder eller ansvar blandas.

## Dokument
- [ARCHITECTURE.md](ARCHITECTURE.md) – målbild, ansvar, moduler, integrationer, datamodell, säkerhet och faser.
- [IDEAS_AND_DECISIONS.md](IDEAS_AND_DECISIONS.md) – idéregister, fastlagda principer, öppna frågor och beslutslogg.

## Grundprinciper
- CROW Platform ska fungera utan GRC-modulen.
- GRC ska fungera utan Edge, OVK eller CROW Security.
- Evidens ska vara spårbar, versionsbunden och knuten till en kontroll och ett avgränsat scope.
- Systemet får föreslå riskbedömningar, men ansvarig människa godkänner riskacceptans, undantag och formell compliance-status.
- ISO 27001, SOC 2 och NIS2 är referensramverk för kartläggning och stöd; verktyget får inte påstå att en kund är certifierad, revisionsgodkänd eller rättsligt compliant enbart utifrån insamlade signaler.

## Status
Endast dokumentation finns här. Inga GRC-funktioner har implementerats genom denna PR.
