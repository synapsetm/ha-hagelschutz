# Hagelschutz – einfach automatisch (Home Assistant)

> [!WARNING]
> **Entwicklungsstand — Funktionskontrolle steht aus.**
>
> Der API-Zugriff ist inzwischen gegen eine reale Anlage bestätigt (`HTTP 200`).
> Was noch fehlt, ist der vollständige Durchlauf in Home Assistant inklusive
> Testalarm über das VKF-Portal. Bis dahin nicht als alleiniger Hagelschutz
> verlassen.
>
> Beachte ausserdem: Sobald das Objekt im Portal aktiv ist, meldet die VKF per
> SMS/E-Mail an Erst- und Zweitkontakt, wenn eine Stunde am Stück keine Daten
> abgeholt werden.

Custom Integration, die das Hagelwarnsignal der VKF/VKG als Binary Sensor in Home
Assistant bereitstellt. Sie ersetzt die Signalbox: Home Assistant pollt die
VKF-Schnittstelle selbst und fährt die Storen über eigene Automationen hoch.

- **Domain:** `hagelschutz`
- **IoT-Class:** `cloud_polling`, festes Intervall von 120 Sekunden
- **Schnittstelle:** `https://meteo.netitservices.com/api/v1` (Details in
  [`docs/vkf-schnittstellenbeschreibung.pdf`](docs/vkf-schnittstellenbeschreibung.pdf))

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

### HACS
1. HACS → Integrationen → ⋮ → *Custom repositories*
2. Repository `https://github.com/synapsetm/ha-hagelschutz`, Kategorie *Integration*
3. Installieren, Home Assistant neu starten

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

Die Integration liefert nur das Signal. Was mit den Storen passiert, gehört in
eigene Automationen:

```yaml
automation:
  - alias: "Hagel – Storen hoch"
    triggers:
      - trigger: state
        entity_id: binary_sensor.hagelschutz_hagelwarnung
        to: "on"
    actions:
      - action: scene.create
        data:
          scene_id: storen_vor_hagel
          snapshot_entities: [cover.storen_sued, cover.storen_west]
      - action: cover.open_cover
        target:
          entity_id: [cover.storen_sued, cover.storen_west]

  - alias: "Hagel – Entwarnung"
    triggers:
      - trigger: state
        entity_id: binary_sensor.hagelschutz_hagelwarnung
        to: "off"
        for: "00:20:00"
    actions:
      - action: scene.turn_on
        target:
          entity_id: scene.storen_vor_hagel

  - alias: "Hagelschutz – Ausfall melden"
    triggers:
      - trigger: state
        entity_id: binary_sensor.hagelschutz_hagelwarnung
        to: "unavailable"
        for: "00:15:00"
    actions:
      - action: notify.mobile_app_<geraet>
        data:
          message: "Hagelschutz-API seit 15 Minuten nicht erreichbar."
```

Der `scene.create`-Snapshot ersetzt das zweite Signal der Signalbox, das die
Storen nach der Entwarnung in die Ausgangsposition zurückfährt.

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
- [`docs/vkf-schnittstellenbeschreibung.pdf`](docs/vkf-schnittstellenbeschreibung.pdf) — offizielle VKF-Schnittstellenbeschreibung

## Lizenz

MIT — siehe [`LICENSE`](LICENSE).
