# Postup implementácie

Každá etapa sa uloží do samostatného commitu priamo na vetve `main`
podľa aktualizovaného pokynu používateľa. Ďalšia etapa
vyžaduje výslovné potvrdenie používateľa podľa AGENTS.md.

1. **Pripravené:** kostra, README, konfigurácia, závislosti a prázdne adresáre.
2. **Napísané, nespustené:** aktuálne univerzum a infraštruktúra sťahovania;
   cache a proveniencia. Historické režimy explicitne zlyhajú bez overeného zdroja.
3. **Napísané, nespustené:** validácia cien, synchronizácia, výnosy,
   anualizácia, report kvality a oneskorenie bezrizikovej sadzby.
4. **Napísané, nespustené:** Markowitz optimalizácia cez CLARABEL,
   regularizácia, okná, lagovaná sadzba, núdzové pravidlo, filter a koncentrácia.
5. **Napísané, nespustené:** päť stratégií, next-close exekúcie,
   účtovanie po poplatkoch, nezáporná hotovosť, drift a oddelené počty/obrat.
6. Metriky, podperiódy a štyri statické grafy.
7. Orchestrácia, notebook a generátor záverov; budúce spustenie jedným príkazom.
8. Zdrojové súbory offline testov so syntetickými vstupmi, bez spustenia.

Po etape 8 sa implementácia zastaví. Inštalácia, testovanie, sťahovanie dát
aj výpočty vyžadujú samostatné povolenie. Zatiaľ nič z toho neprebehlo.
