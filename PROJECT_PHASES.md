# Postup implementácie

Každá etapa sa uloží do samostatného commitu priamo na vetve `main`
podľa aktualizovaného pokynu používateľa. Ďalšia etapa
vyžaduje výslovné potvrdenie používateľa podľa AGENTS.md.

1. **Pripravené:** kostra, README, konfigurácia, závislosti a prázdne adresáre.
2. **Implementované:** aktuálne univerzum a infraštruktúra sťahovania;
   cache a proveniencia. Historické režimy explicitne zlyhajú bez overeného zdroja.
3. **Implementované:** validácia cien, synchronizácia, výnosy,
   anualizácia, report kvality a oneskorenie bezrizikovej sadzby.
4. **Implementované:** Markowitz optimalizácia cez CLARABEL,
   regularizácia, okná, lagovaná sadzba, núdzové pravidlo, filter a koncentrácia.
5. **Implementované:** päť stratégií, next-close exekúcie,
   účtovanie po poplatkoch, nezáporná hotovosť, drift a oddelené počty/obrat.
6. **Implementované:** metriky, správne počiatočné hodnoty podperiód,
   koncentrácia, štyri statické grafické funkcie a explicitný CSV/PNG export.
7. **Implementované:** orchestrácia, notebook bez výstupov,
   generátor záverov, manifest behu a návod na budúce spustenie jedným príkazom.
8. **Implementované:** zdrojové súbory offline testov so syntetickými
   vstupmi a blokovanou sieťou. Testy následne prešli po osobitnom povolení.

Po etape 8 sa implementácia zastavila. Používateľ následne samostatne povolil
inštaláciu, testovanie, sťahovanie dát a výpočty; tieto kroky už prebehli.

## Samostatne schválená validácia a beh

29 offline testov prešlo. Hlavný download, preprocessing, backtest, metriky
a grafy sa dokončili; podrobnosti sú v `validation/README.md`.
