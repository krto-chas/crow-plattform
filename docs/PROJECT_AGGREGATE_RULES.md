# Project Aggregate Rules

1. Dokument-ID:n är unika inom projektet.
2. Claim-ID:n är unika inom projektet.
3. Ett Claim måste referera till ett aktivt projektdokument.
4. En aktiverad modul måste finnas i Module Registry.
5. Projektet får inte köras innan readiness-valideringen passerar.
6. Varje körning får ett stabilt run-ID.
7. Varje konflikt får en separat Decision Graph.
8. Olösta authority decisions leder till Human Review.
9. Projektmodellen lagrar endast publika modulidentiteter, inte privata pluginobjekt.
10. Projektets statusändringar sker genom aggregatets metoder.
