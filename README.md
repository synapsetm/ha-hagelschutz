# Hagelschutz – einfach automatisch (Home Assistant)

[![HACS: Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Release](https://img.shields.io/github/v/release/synapsetm/ha-hagelschutz)](https://github.com/synapsetm/ha-hagelschutz/releases)
[![Validate](https://github.com/synapsetm/ha-hagelschutz/actions/workflows/validate.yml/badge.svg)](https://github.com/synapsetm/ha-hagelschutz/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Custom Integration, die das Hagelwarnsignal der VKF/VKG als Binary Sensor in Home
Assistant bereitstellt. Sie ersetzt die Signalbox: Home Assistant pollt die
VKF-Schnittstelle selbst und fährt die Storen über eigene Automationen hoch.

- **Domain:** `hagelschutz`
- **IoT-Class:** `cloud_polling`, festes Intervall von 120 Sekunden
- **Schnittstelle:** `https://meteo.netitservices.com/api/v1`
- **Status:** gegen eine reale Anlage verifiziert — Funktionskontrolle per
  Testalarm durchlaufen, `currentState` 0 und 2 in Home Assistant bestätigt.
  Ausfallpfad ebenfalls geprüft: Bei gestopptem Polling werden die Entitäten
  `unavailable`, und `Hagelschutz – Ausfall` meldet sich nach 15 Minuten

> [!IMPORTANT]
> Sobald die Alarmkette im VKF-Portal aktiviert ist, meldet die VKF per
> SMS/E-Mail an Erst- und Zweitkontakt, wenn eine Stunde am Stück keine Daten
> abgeholt werden. Kurze Neustarts sind unkritisch, längere Ausfälle nicht.

## Die `hwtypeId`

Der Wert ist **objektspezifisch** und wird von der VKF vergeben. Er steht weder
in der Schnittstellenbeschreibung noch zwingend im Portal — auf dem Datenblatt
ist das Feld „Schnittstelle (hwtypeId)" ein Platzhalter, den die VKF pro Anlage
ausfüllt. Beobachtete Werte liegen im dreistelligen Bereich, sind also nicht
sinnvoll zu erraten.

Falls du ihn nicht hast: bei der VKF anfragen. Woran du erkennst, dass er fehlt
oder falsch ist:

| Antwort | Bedeutung |
|---|---|
| `200` + JSON | Beide Werte stimmen |
| `400`, leerer Body | Seriennummer bekannt, aber `hwtypeId` passt nicht |
| `404` | Seriennummer unbekannt |

## Undokumentierte Response-Felder

Die reale Antwort enthält mehr, als die Schnittstellenbeschreibung nennt:

```json
{"currentState": 0, "newProgVer": 0, "hailState": 0, "windState": 0}
```

Dokumentiert und damit verbindlich ist allein `currentState`. Diese Integration
wertet nur dieses Feld aus. `hailState`, `windState` und `newProgVer` sind
undokumentiert, ihre Bedeutung ist nicht zugesichert und sie können jederzeit
verschwinden — `windState` deutet auf ein Windwarnsignal hin, ist aber nicht
bestätigt.

## Installation

### HACS (empfohlen)

Diese Integration ist **nicht** im HACS-Standardkatalog. Sie wird als *Custom
repository* hinzugefügt — einmalig, danach kommen Updates wie bei jeder anderen
HACS-Integration.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=synapsetm&repository=ha-hagelschutz&category=integration)

Falls der Knopf nicht funktioniert, von Hand:

1. HACS → ⋮ (oben rechts) → *Custom repositories*
2. Repository `https://github.com/synapsetm/ha-hagelschutz`, Typ *Integration*, → *Add*
3. *Hagelschutz – einfach automatisch* suchen → *Download*
4. Home Assistant neu starten

### Manuell
`custom_components/hagelschutz/` in den `config/custom_components/`-Ordner kopieren
und Home Assistant neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → *Integration hinzufügen* → **Hagelschutz**.

| Feld | Bedeutung |
|------|-----------|
| `device_id` | 12-stelliger eindeutiger Identifier (Seriennummer / MAC-Adresse) aus dem VKF-Portal |
| `hwtype_id` | Ganzzahl, bezeichnet den Gerätetyp |

Die Eingabe wird mit einem einmaligen Poll geprüft. Es gibt **keine
YAML-Konfiguration** und keinen Options-Flow — das Poll-Intervall ist von der VKF
mit 120 Sekunden vorgeschrieben und deshalb fix.

> **Die `device_id` ist das Geheimnis dieser Schnittstelle.** Es gibt keinen
> API-Key und keinen Header-Auth. Die ID gehört nicht ins Repository, nicht in
> Screenshots und nicht in Log-Ausgaben. Die Diagnostics maskieren sie.

## Entitäten

| Entität | Beschreibung |
|---------|--------------|
| `binary_sensor.hagelschutz_hagelwarnung` | `on`, sobald `currentState != 0`. `device_class: safety`. Attribute: `current_state` (roher Int), `test_alarm` (bool) |
| `sensor.hagelschutz_status` | Diagnose-Enum `no_hail` / `hail` / `test_alarm`. Nur zur Funktionskontrolle |

`currentState` kennt drei Werte: `0` keine Warnung, `1` Hagelwarnung, `2`
Hagelwarnung durch Testalarm. Der Binary Sensor unterscheidet bewusst **nicht**
zwischen `1` und `2` — der Testalarm existiert genau dazu, die ganze Wirkungskette
inklusive Storen zu prüfen.

Schlägt der Poll fehl, werden die Entitäten `unavailable`. Das ist gleichzeitig
der Watchdog: darauf lässt sich eine Ausfall-Automation bauen.

> Der Entity-Suffix folgt dem angezeigten Namen und ist damit sprachabhängig
> (`_hagelwarnung` in einer deutschen Installation, `_hail_warning` in einer
> englischen). Die Entity-ID einmal auf einen festen Wert umbenennen, bevor
> Automationen darauf verweisen.

## Automationen

Die Integration liefert nur das Signal. Was damit geschieht, gehört in eigene
Automationen. Vier ergeben zusammen ein vollständiges Bild — nur die erste
greift in die Anlage ein, die anderen drei informieren.

| Automation | Auslöser | Wirkung |
|---|---|---|
| `Hagelschutz – Storen hoch` | Warnung geht an | Storen hoch, Meldung |
| `Hagelschutz – Entwarnung` | Warnung 20 min aus | Meldung: Storen können herunter |
| `Hagelschutz – Ausfall` | 15 min `unavailable` | Meldung: kein Signal mehr |
| `Hagelschutz – Wiederherstellung` | wieder erreichbar | Meldung: Signal zurück |

Vor dem Übernehmen drei Platzhalter ersetzen: `<geraet>` durch dein
Companion-App-Gerät (zu finden unter *Entwicklerwerkzeuge → Aktionen*, Suche
`notify.mobile_app`), die `cover.`-Entitäten durch deine, und
`binary_sensor.hagelschutz_hagelwarnung` durch die tatsächliche Entity-ID.

```yaml
automation:
  - alias: "Hagelschutz – Storen hoch"
    description: "Fährt die Storen hoch, sobald eine Hagelwarnung eintrifft."
    triggers:
      - trigger: state
        entity_id: binary_sensor.hagelschutz_hagelwarnung
        to: "on"
    actions:
      # Erst handeln, dann melden — die Storen sollen auch hochfahren,
      # wenn die Benachrichtigung scheitert.
      - action: cover.open_cover
        target:
          entity_id: [cover.storen_sued, cover.storen_west]
      - action: notify.mobile_app_<geraet>
        data:
          title: >-
            {{ 'Testalarm Hagel'
               if state_attr('binary_sensor.hagelschutz_hagelwarnung', 'test_alarm')
               else 'Hagelwarnung' }}
          message: "Storen wurden hochgefahren."
    mode: single

  - alias: "Hagelschutz – Entwarnung"
    description: "Meldet, dass die Storen wieder heruntergefahren werden können."
    triggers:
      # from: "on" verhindert eine Entwarnung für einen Hagel, den es nie gab:
      # ohne das feuert auch der Wechsel von unavailable auf off.
      - trigger: state
        entity_id: binary_sensor.hagelschutz_hagelwarnung
        from: "on"
        to: "off"
        for: "00:20:00"
    actions:
      - action: notify.mobile_app_<geraet>
        data:
          title: "Hagel vorbei"
          message: "Entwarnung seit 20 Minuten. Storen können wieder herunter."
    mode: single

  - alias: "Hagelschutz – Ausfall"
    description: "Meldet, wenn die Schnittstelle länger kein Signal liefert."
    triggers:
      # 15 Minuten filtern Neustarts und kurze Netzaussetzer weg.
      - trigger: state
        entity_id: binary_sensor.hagelschutz_hagelwarnung
        to: "unavailable"
        for: "00:15:00"
    actions:
      - action: notify.mobile_app_<geraet>
        data:
          title: "Hagelschutz gestört"
          message: "Schnittstelle seit 15 Minuten nicht erreichbar."
    mode: single

  - alias: "Hagelschutz – Wiederherstellung"
    description: "Meldet, dass wieder ein Signal ankommt."
    triggers:
      - trigger: state
        entity_id: binary_sensor.hagelschutz_hagelwarnung
        from: "unavailable"
        for: "00:02:00"
    actions:
      - action: notify.mobile_app_<geraet>
        data:
          title: "Hagelschutz wieder online"
          message: "Schnittstelle wieder erreichbar."
    mode: single
```

### Warum die Meldungen nicht optional sind

`unavailable` bedeutet **nicht** „kein Hagel", sondern „unbekannt". Solange die
Entität nicht erreichbar ist, gibt es kein `on` — die Storen-Automation feuert
nie. Das ist ein stiller Ausfall, den ohne `Hagelschutz – Ausfall` niemand
bemerkt.

Die VKF-Alarmkette greift ebenfalls, aber erst nach einer Stunde ohne
Datenabholung und nur im Zeitfenster 08:00–22:00. Die lokale Meldung kommt nach
15 Minuten und rund um die Uhr — sie ersetzt die Alarmkette nicht, sie kommt ihr
zuvor. Ist Home Assistant selbst tot, bleibt nur die Alarmkette; auch deshalb
gehört sie aktiviert.

Beides lässt sich in einem Durchgang prüfen: Integration deaktivieren
(*Einstellungen → Geräte & Dienste → Hagelschutz → ⋮ → Deaktivieren*), eine
Stunde warten, danach wieder aktivieren. Die lokale Meldung muss nach
15 Minuten kommen, die der VKF nach etwa einer Stunde. Den Test zwischen 08:00
und 20:00 starten, damit die Stunde noch ins Meldefenster fällt, und einen Tag
ohne Gewitterprognose wählen — währenddessen besteht kein Hagelschutz.

### Kein automatisches Herunterfahren

Die Signalbox, die diese Integration ersetzt, sendet nach der Entwarnung ein
zweites Signal und fährt die Storen in die Ausgangsposition zurück. Hier ist das
**bewusst nicht** nachgebaut.

Der Grund ist Sicherheit: Zwischen Warnung und Entwarnung liegen Minuten bis
Stunden. In dieser Zeit kann jemand in den Garten gegangen sein oder eine
Terrassentür geöffnet haben. Ein Storen, der ohne Anwesenheit von selbst
herunterfährt, kann jemanden aussperren oder eine Tür blockieren. Hochfahren ist
in jeder Situation ungefährlich, Herunterfahren nicht. Deshalb meldet
`Hagelschutz – Entwarnung` nur, statt zu handeln.

Wer es dennoch automatisieren will, nimmt vor dem Hochfahren einen
`scene.create`-Snapshot der Positionen und stellt ihn nach der Entwarnung mit
`scene.turn_on` wieder her — abgesichert über eine Anwesenheits- oder
Türkontakt-Bedingung.

> [!NOTE]
> Die VKF-Funktionskontrolle sieht vor, dass die Storen nach dem Deaktivieren des
> Testalarms wieder herunterfahren. Ohne automatisches Herunterfahren ist dieser
> Schritt manuell auszuführen. Wenn du das Abnahmeprotokoll unterschreibst, kläre
> vorher mit der VKF, ob das für dein Objekt so akzeptiert wird.

## Betriebshinweise

1. **Alarmkette der VKF.** Holt die Gebäudesteuerung eine Stunde am Stück keine
   Daten, informiert die VKF den hinterlegten Erst-/Zweitkontakt per SMS/E-Mail
   (Zeitfenster 08:00–22:00, sonst am Folgetag ab 08:00; Zweitmeldung am nächsten
   Werktag). Kurze HA-Neustarts sind unkritisch — längere Entwicklungspausen mit
   abgeschalteter Integration lösen echte Meldungen aus. Während der Entwicklung
   gegen Mocks arbeiten oder die Downtime unter einer Stunde halten.
2. **Testalarm.** Über das VKF-Portal auslösbar; `currentState` springt innerhalb
   von zwei Minuten auf `2`. Das Portal-Log zeigt „Hagelwarnung eingetroffen“ und
   „Signalbox hat Hagelwarnung abgeholt“ — Letzteres bestätigt, dass wirklich
   diese Integration gepollt hat.
3. **Kein aggressiveres Polling.** 120 Sekunden sind vorgeschrieben. Keine
   `homeassistant.update_entity`-Schleifen, keine kürzeren Intervalle.
4. **Error-Reports.** Bei einem API-seitigen Fehler (HTTP-Status ≠ 200, kaputtes
   JSON) setzt die Integration einen `errorLogs`-POST ab, höchstens einmal pro
   15 Minuten. Reine Verbindungsfehler werden nicht gemeldet — der POST würde
   ohnehin scheitern.

## Fehlersuche

Debug-Logging in `configuration.yaml` einschalten und Home Assistant neu starten:

```yaml
logger:
  default: warning
  logs:
    custom_components.hagelschutz: debug
```

Beim Fehler *„Unerwarteter Fehler"* im Setup-Dialog steht der Grund als
`ERROR`-Zeile im Log (`Unexpected API response: ...`), auch ohne Debug-Logging.
Mit Debug-Logging kommt zusätzlich der Response-Body dazu.

Die Schnittstelle lässt sich auch ohne Home Assistant direkt prüfen:

```bash
curl -sS -i "https://meteo.netitservices.com/api/v1/devices/<deviceId>/poll?hwtypeId=<hwtypeId>"
```

| Antwort | Bedeutung |
|---------|-----------|
| `200` + `{"currentState": 0}` | Beide Werte stimmen |
| `401` / `403` / `404` | `deviceId` falsch oder Gerät nicht freigeschaltet |
| `400` | meist eine unbekannte oder fehlende `hwtypeId` |
| `5xx` | serverseitig — später erneut versuchen |

> Debug-Logs und `curl -i`-Ausgaben können die `deviceId` enthalten. Vor dem
> Teilen in einem Issue maskieren.

## Entwicklung

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-test.txt ruff
ruff check .
pytest
```

Die Tests mocken die HTTP-Schicht mit `aioresponses`; es geht nie ein Request an
die echte VKF-Schnittstelle.

## Dokumente

- [`docs/SPEC-hagelschutz-ha-integration.md`](docs/SPEC-hagelschutz-ha-integration.md) — Implementierungs-Spec

Die offizielle VKF-Schnittstellenbeschreibung liegt diesem Repository bewusst
**nicht** bei: Sie wird bei der Anmeldung von der VKF zugestellt, und eine Kopie
hier würde veralten. Der in diesem README dokumentierte Vertrag ist gegen eine
reale Anlage verifiziert — verbindlich ist im Zweifel das Dokument der VKF.

## Lizenz

MIT — siehe [`LICENSE`](LICENSE).
