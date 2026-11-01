# Sport-EPG

Aktualisiert die 20 oeffentlichen Rytec-/Spanien-Quellen alle zwei Tage, verankert am 30. Oktober 2026. Der erste Versuch ist um 06:17 Uhr Schweizer Zeit geplant. Weitere Pruefungen erfolgen taeglich um 08:17, 10:17, 14:17, 18:17 und 22:17 Uhr. Sommer- und Winterzeit werden beruecksichtigt.

Vor jedem Download wird die letzte faellige Ausgabe mit der veroeffentlichten status.json und den Release-Dateien verglichen: Erzeugungsdatum, Vollstaendigkeit, Upload-Zeiten und SHA-256-Pruefsummen muessen passen. Ist alles aktuell, erfolgt kein neuer Download. Fehlgeschlagene oder ausgefallene Versuche werden beim naechsten Prueftermin nachgeholt, auch an einem sonstigen Pausentag. Monats- und Jahreswechsel unterbrechen den Rhythmus nicht. Manuell kann ueber Run workflow mit force=true eine Neuerstellung erzwungen werden.

Die Ausgabe wird erst nach erfolgreicher Pruefung aller Quellen veroeffentlicht. Vor dem Ersetzen werden die vorherigen Dateien gesichert. XML und GZ werden zuerst hochgeladen und kontrolliert; status.json folgt als letzter Erfolgsmarker. Bei einem erkannten Uploadfehler wird die vorherige Ausgabe wiederhergestellt. Die Release-Dateien sind technisch nicht atomar austauschbar; ein abgebrochener Runner kann die Wiederherstellung verhindern. Der naechste Prueflauf erkennt unvollstaendige oder abweichende Dateien und versucht eine erneute Aktualisierung.

Jede erfolgreiche Veroeffentlichung protokolliert last-success.json als Commit. Das haelt die Repository-Aktivitaet aufrecht und verhindert eine unbeabsichtigte Inaktivitaet bei ausschliesslicher Nutzung von Release-Dateien. Protokoll-Commits loesen keine weiteren EPG-Laeufe aus.

GitHub garantiert keine punktgenauen oder lueckenlosen geplanten Starts. Mehrere Pruefzeiten fangen einzelne verpasste Starts ab; einen vollstaendigen Ausfall von GitHub Actions oder dessen Zeitplanung kann dieser Workflow nicht ueberwinden. Es ist kein unabhaengiger externer Scheduler eingerichtet.

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

Download- und Validierungsfehler lassen die vorherige Ausgabe unveraendert. Bei Uploadfehlern wird die Wiederherstellung versucht. Unter Actions kann der Auftrag bei Bedarf auch manuell gestartet werden.

GitHubs Begrenzungen fuer geplante Auftraege gelten weiterhin. Fehlgeschlagene Laeufe sind unter Actions sichtbar; Benachrichtigungen richten sich nach den persoenlichen GitHub-Einstellungen. Es werden keine zusaetzlichen Nachrichten an Dritte gesendet.

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

