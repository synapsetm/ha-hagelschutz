# Spec: Home Assistant Custom Integration «Hagelschutz – einfach automatisch»

Vorlage für Claude Code. Domain: `Hagelschutz`. Ziel: HACS-fähige Custom Integration,
die das Hagelwarnsignal der VKF/VKG als Binary Sensor in Home Assistant bereitstellt.

## 1. API-Kontrakt (verbindlich, aus der VKF-Schnittstellenbeschreibung)

### Poll
```
GET https://meteo.netitservices.com/api/v1/devices/{deviceId}/poll?hwtypeId={hwtypeId}
```
- `deviceId`: 12-stelliger eindeutiger Identifier (Seriennummer / MAC-Adresse)
- `hwtypeId`: Integer, bezeichnet den Gerätetyp
- **Kein Header-Auth, kein API-Key.** Die `deviceId` ist faktisch das Geheimnis.
- Poll-Intervall ist mit **120 Sekunden vorgeschrieben** (Prognose wird alle 5 min neu
  gerechnet). Nicht konfigurierbar machen, hart auf 120 s setzen.

Response 200:
```json
{ "currentState": 0 }
```
| Wert | Bedeutung |
|------|-----------|
| 0 | keine Hagelwarnung |
| 1 | Hagelwarnung |
| 2 | Hagelwarnung durch Testalarm ausgelöst |

Die Spec empfiehlt ausdrücklich, nur zwischen `0` und `non-zero` zu unterscheiden.
Das Verhalten (Storen hoch) muss bei 1 und 2 identisch sein — der Testalarm ist genau
dafür da, die Wirkungskette zu prüfen.

Fehlerfall: HTTP-Status-Error mit Message.

### Error-Report (optional, aber implementieren)
```
POST https://meteo.netitservices.com/api/v1/devices/{deviceId}/errorLogs
Content-Type: application/json

{ "errlog": "<payload>" }
```

## 2. Dateistruktur

```
custom_components/hagelschutz/
    __init__.py
    manifest.json
    config_flow.py
    coordinator.py
    binary_sensor.py
    sensor.py            # optional, Diagnostic
    const.py
    strings.json
    translations/de.json
    translations/en.json
tests/
    conftest.py
    test_config_flow.py
    test_coordinator.py
    fixtures/poll_no_hail.json
    fixtures/poll_hail.json
    fixtures/poll_test_alarm.json
hacs.json
README.md
```

## 3. manifest.json

```json
{
  "domain": "hagelschutz",
  "name": "Hagelschutz – einfach automatisch",
  "codeowners": ["@<github-user>"],
  "config_flow": true,
  "documentation": "https://github.com/<user>/ha-hagelschutz",
  "integration_type": "service",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/<user>/ha-hagelschutz/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

`requirements` bleibt leer — `aiohttp` kommt über
`homeassistant.helpers.aiohttp_client.async_get_clientsession`.

## 4. Config Flow

- Schritt `user`: Felder `device_id` (str) und `hwtype_id` (int).
- Validierung: einmaliger Poll gegen die API.
  - HTTP 200 + parsebares `currentState` → OK
  - 401/403/404 → `invalid_device`
  - Timeout / ClientError → `cannot_connect`
  - alles andere → `unknown`
- `unique_id` = `device_id`, danach `_abort_if_unique_id_configured()`.
- Titel des Entries: `Hagelschutz {device_id}`.
- Kein Options Flow. Es gibt nichts sinnvoll zu konfigurieren; das Intervall ist fix.
- **Keine YAML-Konfiguration** (kein `async_setup` mit Config-Import).

## 5. Coordinator

`HagelschutzCoordinator(DataUpdateCoordinator[int])` in `coordinator.py`:

- `update_interval = timedelta(seconds=120)` aus `const.py`, nicht überschreibbar.
- `_async_update_data()` gibt den rohen `currentState` als `int` zurück.
- Bei Timeout / ClientError / ungültigem JSON → `UpdateFailed`. Damit werden die
  Entities automatisch `unavailable`, was gleichzeitig der Watchdog ist.
- Request-Timeout 30 s (kleiner als das 120-s-Intervall).
- Bei `UpdateFailed` zusätzlich einen `errorLogs`-POST absetzen, aber:
  - nur wenn der Fehler *nicht* ein reiner Verbindungsfehler ist (sonst schlägt der
    POST ohnehin fehl),
  - höchstens einmal pro 15 Minuten (einfacher Timestamp-Guard), kein Spam,
  - Fehler im POST selbst nur loggen, niemals durchreichen.

## 6. Entities

### `binary_sensor.hagelwarnung` (primär)
- `device_class: BinarySensorDeviceClass.SAFETY`
- `is_on = coordinator.data != 0`
- `translation_key: "hail_warning"`
- `unique_id: f"{entry.entry_id}_hail_warning"`
- Extra state attributes: `current_state` (roher Int), `test_alarm` (bool, `data == 2`)

### `sensor.hagelschutz_status` (optional, `EntityCategory.DIAGNOSTIC`)
- `device_class: ENUM`, `options: ["no_hail", "hail", "test_alarm"]`
- Nur für Debugging/Funktionskontrolle. Automationen sollen den Binary Sensor nutzen.

Beide hängen an einem `DeviceInfo` mit
`identifiers={(DOMAIN, device_id)}`, `manufacturer="VKF/VKG"`,
`model="Hagelschutz – einfach automatisch"`, `configuration_url="https://meteo.netitservices.com"`.

## 7. Tests

- `aioresponses` oder `aiohttp`-Mocking gegen die drei Fixtures.
- Testfälle: Config Flow happy path, Duplikat-Abbruch, `cannot_connect`;
  Coordinator liefert 0/1/2; `UpdateFailed` bei 500 und bei Timeout;
  Binary Sensor `is_on` für alle drei States.
- Fixtures sind trivial: `{"currentState": 0}` / `1` / `2`.

## 8. Fallstricke, die im Code adressiert sein müssen

1. **`deviceId` ist das Geheimnis.** Sie darf nicht ins Repo, nicht in Log-Ausgaben
   und nicht in Diagnostics. `async_get_config_entry_diagnostics` muss sie über
   `async_redact_data` maskieren.
2. **Alarmkette der VKF.** Holt die Gebäudesteuerung eine Stunde am Stück keine Daten,
   informiert die VKF den hinterlegten Erst-/Zweitkontakt per SMS/E-Mail (Zeitfenster
   08:00–22:00, sonst am Folgetag ab 08:00; Zweitmeldung am nächsten Werktag).
   Konsequenz: Kurze HA-Neustarts sind unkritisch, längere Dev-Pausen mit
   abgeschalteter Integration lösen echte Meldungen aus. Während der Entwicklung
   entweder gegen Mocks arbeiten oder die Downtime unter einer Stunde halten.
3. **Testalarm als Integrationstest.** Über das Portal auslösbar; `currentState`
   springt innerhalb von zwei Minuten auf 2. Das Portal-Log zeigt sowohl
   „Hagelwarnung eingetroffen“ als auch „Signalbox hat Hagelwarnung abgeholt“ —
   Letzteres bestätigt, dass die eigene Integration wirklich gepollt hat.
4. **Kein aggressiveres Polling.** 120 s sind vorgeschrieben, kein
   `async_request_refresh()` in Schleifen, keine Options für kürzere Intervalle.

## 9. Automationen (gehören ins README, nicht in den Code)

```yaml
automation:
  - alias: "Hagel – Storen hoch"
    triggers:
      - trigger: state
        entity_id: binary_sensor.hagelwarnung
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
        entity_id: binary_sensor.hagelwarnung
        to: "off"
        for: "00:20:00"
    actions:
      - action: scene.turn_on
        target:
          entity_id: scene.storen_vor_hagel

  - alias: "Hagelschutz – Ausfall melden"
    triggers:
      - trigger: state
        entity_id: binary_sensor.hagelwarnung
        to: "unavailable"
        for: "00:15:00"
    actions:
      - action: notify.mobile_app_<geraet>
        data:
          message: "Hagelschutz-API seit 15 Minuten nicht erreichbar."
```

Der `scene.create`-Snapshot ersetzt das zweite Signal der Signalbox, das die Storen
nach der Entwarnung in die Ausgangsposition zurückfährt.
