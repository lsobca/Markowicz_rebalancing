# Offline test suite

Testy boli pôvodne napísané bez spustenia v etape 8. Po samostatnom súhlase
používateľa prebehla validácia: 29 testov prešlo, vrátane exportu grafov
a opakovaného dávkového sťahovania. Log je v `validation/pytest.txt`.

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
Úspešný offline beh nenahrádza overenie reálnych zdrojov; ďalšie behy môžu odhaliť nové chyby.
