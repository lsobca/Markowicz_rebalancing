# Offline test source — not executed

Etapa 8 obsahuje iba zdrojové testy. Žiadny test, import modulov, kontrola
syntaxe ani inštalácia závislostí neboli v rámci implementácie vykonané.

Po samostatnom povolení validácie, z koreňa repozitára s nainštalovanými
závislosťami, je určený príkaz `python -m pytest tests`.

Sieťové pripojenia sú v každom teste blokované fixture. HTTP chyby, cache,
roster a cenové dáta sú syntetické. Test analytického optima vyžaduje lokálny
CLARABEL; nejde o sieťový test. Integračný test používa syntetické ceny
2004–2025 a deterministickú náhradu optimalizátora, takže samostatne overuje
časovanie a účtovanie piatich účtov, nie kvalitu odhadu váh.

Pokrytie: predvoľby, výnimočné uzávery a prvé udalosti, úvodné a priebežné
poplatky, drobné obchody, strict > materiálny prah, strict < filter váh,
kladný excess analytický výsledok, núdzové pravidlo a zlyhanie solvera,
regularizácia, koncentrácia, asymetrické okná, nezávislosť od budúcich cien,
FRED lag cez sviatok, absencia backfill, chýbajúce a zanikajúce cenové rady,
požadovaný Adj Close, checksum/vintage cache, historické source errors,
celkové metriky a presné otvorenia podperiód.

Syntetické testy nepreukazujú správnosť skutočných korporátnych udalostí,
licencie, historických zdrojov ani aktuálnu kompatibilitu vzdialených API.
Samotná existencia testov neznamená, že prešli; budúci beh môže odhaliť chyby.
