# MyHOME
Modernized MyHOME Custom Component for Home Assistant

[![test-coverage](https://github.com/GreenGrassBlueOcean/MyHOME/actions/workflows/test-coverage.yaml/badge.svg)](https://github.com/GreenGrassBlueOcean/MyHOME/actions/workflows/test-coverage.yaml)
[![codecov](https://codecov.io/gh/GreenGrassBlueOcean/MyHOME/graph/badge.svg)](https://codecov.io/gh/GreenGrassBlueOcean/MyHOME)

*This is a completely modernized, async-native fork of the original integration, specifically hardened for legacy MH200 hardware and modern Home Assistant (2025+).*

## 🌟 Modernization Features

1. **Fully Dynamic Auto-Discovery (No more YAML!):**
   The integration has been completely disentangled from file-system based `myhome.yaml` static configurations. Devices are now registered and configured natively through the Home Assistant UI Device Registry. The integration actively queries the OpenWebNet bus to discover all entities out of the box. Native support for complex **F422 Cross-Bus Routing** (e.g. addresses like `18#4#02`) is also completely handled automatically!
   
2. **Native Audio System Support (WHO=16):**
   Full native support for Bticino/MyHome Audio Matrices, compatible with both legacy baseband and **Sound System 2.0 stereo** hardware. Exposes native `media_player` entities for all audio zones with bidirectional state tracking.
   - **Turn On/Off, Source Selection & Volume:** Full support for `turn_on`, `turn_off`, `select_source`, `volume_set`, `volume_up`, and `volume_down`. Source selection correctly addresses stereo amplifier zones (11x–14x).
   - **Absolute Volume Tracking:** Full support for dimension messages (`*#16*where*#1*vol##`), normalizing the 0–31 hardware scale automatically.
   - **Software Mute Emulation:** Since OpenWebNet lacks a native audio Mute function, this integration fully emulates local muting, keeping physical volume levels accurately cached.

3. **🎵 Dynamic Proxy — Stream Music to Your BTicino Zones:**
   The BTicino audio matrix (F441, S0105A) is a **hardware-only analog switch** — it cannot decode IP-based audio streams on its own. This integration bridges that gap with a *Dynamic Proxy* that lets you stream from **Music Assistant**, **Spotify Connect**, or any HA-compatible media source to your wired BTicino zones.

   **How it works (automatically):**
   1. You configure one or more *decoders* (network media players physically connected to the matrix source inputs) via the Options UI.
   2. When Music Assistant or Spotify sends `play_media` to a BTicino zone, the proxy claims an idle decoder, wakes it, routes the matrix to the correct source input, and forwards the stream.
   3. Playback state (title, artist, album art) is mirrored back from the decoder to the zone entity in real time.
   4. When the zone is turned off, the decoder is released back to the pool for other zones.

   **Compatible decoders:**
   Any HA-integrated `media_player` entity with network streaming capability:
   - **squeezelite / piCorePlayer** — Free, runs on any Raspberry Pi with a DAC HAT (e.g. HiFiBerry DAC+). Discovered automatically by Music Assistant.
   - **Cambridge Audio** (CXN, etc.) — High-end network streamer with HA integration. Works with `internet_radio` content type since HA 2024.11.
   - **WiiM Mini / Pro** — Budget-friendly network streamer with AirPlay and HA support.
   - Any DLNA, Chromecast, or AirPlay-capable device exposed as a `media_player` in HA.

   **Key features:**
   | Feature | Description |
   |---|---|
   | Thread-safe pool | `asyncio.Lock`-protected `DecoderPool` prevents race conditions when multiple zones compete for the same decoder |
   | Up to 4 simultaneous streams | One decoder per physical source input (F441 has 4 inputs) |
   | Gain staging (anti-hiss) | Per-decoder `pre_gain` offset keeps the analog signal level high and the amplifier gain low, reducing bus noise |
   | Backward compatible | If no decoders are configured, the entity behaves exactly as before — `PLAY_MEDIA` is not advertised |
   | Auto-reload | Changing decoder config in Options UI rebuilds the pool without restarting HA |

4. **Auto-Detect Dimmable Lights:**
   Dimmers are automatically recognized from the OpenWebNet protocol. When the gateway sends a brightness level or brightness preset event, the light entity is promoted from simple on/off to full brightness control with transition support. No manual configuration needed — the integration learns from the bus traffic. A `customize.yaml` fallback is still supported for manual overrides.

5. **Smart Gateway Configuration:**
   The custom setup flow first attempts to auto-discover the gateway's MAC address and model by fetching the UPnP device descriptor directly from known BTicino ports (`http://<IP>:49153/description.xml`). If the gateway does not support UPnP (e.g., older MH200 models), a manual fallback step is presented instead. This eliminates the need to manually look up the MAC address for most modern gateways (F454, MH202, MH201).

6. **MH200 & Stability Hardening:**
   Resolved the fatal "Listener Death" bugs prevalent in the original library. 
   - Strict 120-second active watchdogs drop permanently hung TCP sockets efficiently.
   - Exponential Backoff routines (`2s -> 60s`) guard against embedded gateway DDoS on power restoration.
   - Polling queries (`SCAN_INTERVAL`) drastically reduced by default for passive sensors.
   - Native integration caching (`ConfigEntryNotReady`) entirely eliminates the infamous "Restart required on first installation" crash loop.

7. **Robust Entity Migration & Registry Integrity:**
   The integration includes self-healing logic for entity IDs. On startup, it automatically detects and corrects orphaned or mis-named entities from previous installations, reverting entity IDs back to the standard `light.light_XX` / `cover.cover_XX` format. Legacy `customize.yaml` friendly names are transparently absorbed and applied without requiring any manual re-configuration.

## ⚙️ Installation & Configuration

### 1. Install via HACS (Recommended)
You can install this integration as a Custom Repository via HACS!
1. Go to HACS -> Integrations -> Click the three dots (top right) -> Custom repositories
2. Add this repository URL and select `Integration` as the category.
3. Restart Home Assistant.

### 2. Add the Integration in Home Assistant
**Important:** Do *not* use `configuration.yaml` for this integration. The legacy `myhome.yaml` approach has been completely disabled in favor of modern UI-driven architecture.

1. Go to **Settings -> Devices & Services -> Add Integration**.
2. Search for `MyHOME`.
3. The component will automatically search your local network via SSDP for compatible BTicino gateways (e.g., MH200, F454, MyHomeServer1).
4. If no gateways are found automatically, select "Custom" and enter your gateway's IP address and port. The integration will try to auto-detect the MAC address and model via UPnP. If that fails (e.g., on legacy MH200 gateways), a manual entry form is presented.
5. Enter your gateway's OpenWebNet password when prompted.

### 3. Entity Naming & Discovery
Once connected, the integration strictly uses **Auto-Discovery** to find your Lights, Switches, Covers, and Audio Zones.
Simply use your physical wall switches to interact with your house. Home Assistant will capture the physical bus events, dynamically generate the devices in your dashboard (naming them by their hardware address, e.g., `Light 18`, `Cover 18#4#02`), and store them permanently!

To assign human-readable names (like "Kitchen Lights"):
*   **The Modern Way:** Click on the generated Entity in the Home Assistant UI (`Settings -> Devices`), click the gear icon, and rename it natively.
*   **The Power-User Way:** Use Home Assistant's native [customize.yaml](https://www.home-assistant.io/docs/configuration/customizing-devices/) feature to bulk-rename entities without touching the underlying integration logic.

### 4. Audio Zone Controls
Audio zones are automatically discovered as `media_player` entities when any sound system traffic is detected on the bus. The supported features include:

| Feature | Method |
|---|---|
| Turn On/Off | Standard HA media player controls |
| Volume Up/Down | Step-based volume adjustment |
| Volume Slider | Absolute volume set (0–31 → normalized 0.0–1.0) |
| Source Selection | **Soft-Muted Compound Routing** (See Note Below) |
| Mute | Software-emulated (caches volume, sets to 0, restores on unmute) |

#### F441M Source Routing Architecture
The F441M audio matrix uses **compound stereo addresses** for source routing. When Home Assistant selects a source, the integration sends a 3-step sequence:

1. **Soft Mute** — `*16*13*<zone>##` (stereo OFF) to silence the amplifier before switching.
2. **Compound Route** — `*16*3*1<source><zone_digit>##` to cross-connect the matrix relay.
   - Example: Route zone `21` to source `3` → `*16*3*131##` (source_base=13, zone_digit=1).
3. **Unmute** — `*16*3*<zone>##` (stereo ON) to restore audio after the relay settles.

The F441M matrix automatically activates the target source device and deactivates the previous one on the bus. This is the same command sequence used by the physical wall panels.

> **Legacy Note (TiMH200 Upload Bug):**
> If you need to program scenarios on a legacy **MH200** using the `Configurator TiMH200` software on Windows 10/11, the "Upload" button may fail with an `invalid project file format` error. Fix: right-click `TiMH200.exe` → Properties → Compatibility → set to **Windows XP (Service Pack 3)** and **Run as Administrator**. Note that the MH200 does not support CEN/CEN+ triggering over IP.

For **manual OWN commands** (e.g., via the `myhome.send_message` service), refer to the OpenWebNet specification for WHO=16.

### 5. Setting Up Streaming (Dynamic Proxy)

To stream from Music Assistant, Spotify Connect, or other services to your BTicino audio zones, you need at least one **decoder** — a network media player physically connected to one of the matrix source inputs via RCA or 3.5mm.

#### Prerequisites
- A BTicino audio matrix (F441, S0105A, or similar) with at least one free source input
- A network-capable media player wired to that input, integrated into Home Assistant as a `media_player` entity

#### Configuration
1. Go to **Settings → Devices & Services → MyHOME → Configure**.
2. Scroll to the **Decoder** section.
3. For each connected decoder, fill in:
   - **Entity:** The `media_player` entity ID of the decoder (e.g. `media_player.cambridge_audio_cxn`)
   - **Source:** The BTicino source input number (1–4) the decoder is physically wired to
   - **Pre-gain:** A volume offset percentage (0–50) to optimise the analog signal-to-noise ratio. Recommended values:
     - `0` for decoders with fixed line-level output (e.g. Cambridge Audio with Pre-Amp OFF)
     - `15–20` for software-level decoders (e.g. squeezelite on a HiFiBerry DAC)
     - Higher values for particularly noisy setups — start at `30` and reduce if the decoder clips

4. Click **Submit**. The decoder pool is rebuilt immediately without restarting HA.

#### Gain staging explained
The BTicino 2-wire bus introduces inherent analog noise. The `pre_gain` setting drives the decoder volume proportionally higher than the zone volume (`decoder_vol = zone_vol + pre_gain/100`, capped at 1.0), keeping the analog signal level high while reducing the amplifier's noise floor amplification. The result is cleaner audio at lower listening volumes.

### Advanced Usage & Protocol Handling

The underlying OpenWebNet (`OWNd`) package has been exclusively vendored natively into this component (`custom_components/myhome/ownd`), allowing complete downstream control over exact OpenWebNet protocol implementations to maximize reliability.

#### Supported Hardware
| Gateway | UPnP Auto-Discovery | Notes |
|---|---|---|
| F454 | ✅ | Full UPnP support (port 49153) |
| MH202 / MH201 | ✅ | Full UPnP support |
| MH200 | ❌ | Manual MAC entry required; no UPnP descriptor |
| MyHomeServer1 | ✅ | Should work via SSDP |

| Audio Matrix | Decoder Support | Source Inputs |
|---|---|---|
| F441 / F441M | ✅ | 4 stereo inputs |
| S0105A | ✅ | 4 stereo inputs |
| E46ADCN (amplifier) | ✅ | Receives from matrix |

#### Architecture: Dynamic Proxy

```
┌──────────────────┐     ┌───────────────┐     ┌──────────────────┐
│  Music Assistant  │     │  DecoderPool  │     │   F441M Matrix   │
│  / Spotify / MA   │────▶│  (asyncio)    │────▶│   (hardware)     │
│                   │     │               │     │                  │
│  play_media()     │     │  claim()      │     │  select_source() │
│                   │     │  release()    │     │                  │
└──────────────────┘     │  gain_stage() │     │  IN1 ──▶ Zone 3  │
                          └───────────────┘     │  IN2 ──▶ Zone 4  │
                                ▲               │  IN3 ──▶ Zone 5  │
                                │               │  IN4 ──▶ Zone 6  │
                          ┌─────┴──────┐        └──────────────────┘
                          │  Decoders   │
                          │             │
                          │ Cambridge   │──── RCA ───▶ IN1
                          │ squeezelite │──── RCA ───▶ IN2
                          └─────────────┘
```

*(For legacy OpenWebNet implementation documentation, refer to the original bticino open specs).*
