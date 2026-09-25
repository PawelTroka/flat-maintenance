# Budowanie krótkich instrukcji

W katalogu są opisy kart i granice wycinków oryginalnych instrukcji. Uruchom:

```sh
python -m pip install pypdfium2 Pillow
python scripts/manual_fragments/build.py
```

Do przeglądu pojedynczej karty: `python scripts/manual_fragments/build.py --only l12`.

- Współrzędne `box` mają postać `[lewo, góra, prawo, dół]` w punktach PDF, z początkiem w lewym górnym rogu; `page` liczymy od 1.
- Tytuły i częstotliwości pochodzą z głównej listy. `steps`, `safety` i `notes` są krótkimi polskimi opisami; `clips` wskazują oryginalne fragmenty.
- PDF-y w `docs/manuals` pozostają niezmienione. Wycinki są renderowane do PNG, bez przerabiania ich treści. Ten sam wycinek jest współdzielony przez karty.
- Wyniki trafiają do `docs/instrukcje`; manifest zapisuje granice, strony i sumy kontrolne źródeł oraz obrazów.
- Po zmianie specyfikacji obejrzyj każdy zmieniony wycinek i kartę na wąskim ekranie. Nie odcinaj diagramów, zdań ani wymaganych ostrzeżeń. Sam poprawny numer strony nie wystarcza.
- Jeśli zmieniasz instrukcję producenta, sprawdź od nowa granice wycinków i polskie kroki. Nie zakładaj, że nowy PDF ma ten sam układ stron.

Pliki Markdown i PNG są zapisane w repozytorium, więc do korzystania z nich nie trzeba uruchamiać skryptu.
