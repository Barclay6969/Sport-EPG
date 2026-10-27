# Sport-EPG

Aktualisiert die 20 oeffentlichen Rytec-/Spanien-Quellen automatisch jeden Montag und Freitag um 06:00 Uhr Schweizer Zeit. Der GitHub-Zeitplan beruecksichtigt Sommer- und Winterzeit; die Ausfuehrung kann sich bei GitHub-Auslastung verzoegern.

Feste EPG-Adressen nach Einrichtung unter Barclay6969/Sport-EPG:

- https://github.com/Barclay6969/Sport-EPG/releases/download/epg-latest/Sport.xml.gz
- https://github.com/Barclay6969/Sport-EPG/releases/download/epg-latest/Sport.xml

Die Dateien werden als Release-Dateien gespeichert, damit die unkomprimierte XML auch ueber 100 MB gross sein darf. Das Repository muss fuer Downloads ohne Anmeldung oeffentlich sein. Es enthaelt keine IPTV-Liste, Streams oder Zugangsdaten.

In der M3U die bisherigen EPG-Adressen durch diese Kopfzeile ersetzen:

```m3u
#EXTM3U url-tvg="https://github.com/Barclay6969/Sport-EPG/releases/download/epg-latest/Sport.xml.gz" x-tvg-url="https://github.com/Barclay6969/Sport-EPG/releases/download/epg-latest/Sport.xml.gz"
```

Die Sender-IDs bleiben erhalten. Spanische IDs werden zusaetzlich mit Punkten statt Leerzeichen angeboten, um die alte Sport.xml zu unterstuetzen. Keine automatische unscharfe Senderzuordnung. Der Player muss seine EPG-Daten weiterhin regelmaessig abrufen.

## Zusammenfuehrung und Ausfallschutz

Alle 20 Quellen muessen heruntergeladen, entpackt und vollstaendig als XMLTV gelesen werden koennen. Einzelne Sendungen mit ungueltigen oder leeren Zeitintervallen werden ausgelassen und in status.json gezaehlt; bei mehr als 5 Prozent (mindestens sechs Eintraegen) wird abgebrochen. Jede Quelle muss Sender und Programme enthalten. Jede Rytec-Quelle sowie mindestens eine der fuenf spanischen Teilquellen muss noch nicht abgelaufene Programme enthalten. Bereits abgelaufene spanische Teilquellen werden im Statusbericht als outdated markiert; sie werden nicht in die aktuelle Ausgabe aufgenommen. Andernfalls bricht der Auftrag vor der Veroeffentlichung ab; die letzten Release-Dateien bleiben erhalten. GitHub zeigt fehlgeschlagene Laeufe unter Actions an.

Sender werden anhand ihrer ID zusammengefuehrt. Bei mehreren Programmen mit gleicher Sender-ID und identischer UTC-Startzeit gewinnt die erste Quelle in sources.json; Abweichungen werden gezaehlt. Unterschiedliche Startzeiten werden nicht als identische Sendung interpretiert. Zeiten werden nach UTC konvertiert, ohne den Zeitpunkt zu verschieben. Ein Kalenderfilter auf Sport findet nicht statt, entsprechend den umfassenden bisherigen Quellen. Unbekannte fruehere Sonderzuordnungen sind nicht rekonstruiert.

Der Schutz betrifft Download- und Validierungsfehler. GitHub ersetzt mehrere Release-Dateien nicht als eine atomare Transaktion; bei einem seltenen Uploadfehler kann ein einzelnes Asset erneut hochgeladen werden muessen. workflow_dispatch erlaubt einen manuellen Neustart.

Oeffentliche Repositorys koennen geplante Workflows nach laengerer Inaktivitaet automatisch deaktivieren. Actions bei ausbleibenden Updates pruefen. Fuer garantierte langfristige Ausfuehrung waere ein eigener Scheduler erforderlich.

## Einrichtung

1. Neues oeffentliches Repository Sport-EPG anlegen.
2. Inhalt dieses Verzeichnisses einschliesslich .github/workflows nach main hochladen.
3. Unter Actions den ersten Lauf pruefen. Durch den ersten Push startet der Workflow automatisch.
4. Erst nach erfolgreichem Lauf die obige EPG-Adresse in der M3U verwenden.

## Lokal pruefen

Python 3.12, keine Zusatzpakete:

```sh
python -m unittest discover -s tests -v
python merge_epg.py
```
