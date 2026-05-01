# Raspberry Pi ePaper Reader

Simple Python app for a Raspberry Pi Zero 2 W with a WeAct 4.2" ePaper display (Waveshare-compatible `epd4in2_V2` driver).

## Features

- Displays one text page at a time on the ePaper display.
- Hardware button navigation:
  - Previous page: GPIO27 (physical pin 13)
  - Next page: GPIO22 (physical pin 15)
- Software debouncing for button input.
- Local web UI for uploading a replacement `.txt` book.
- Reading progress persisted in `data/state.json`.
- Resume from last saved page on restart.

## Hardware Required

- Raspberry Pi Zero 2 W
- WeAct 4.2 inch ePaper module (Waveshare-compatible `epd4in2_V2`)
- 2 momentary push buttons
- Jumper wires (female-female or female-male depending on your header setup)

## Wiring

### Buttons

The code uses internal pull-ups (`GPIO.PUD_UP`), so each button is wired between GPIO and GND:

- Previous page button: `GPIO27` (physical pin `13`) -> button -> `GND`
- Next page button: `GPIO22` (physical pin `15`) -> button -> `GND`

### ePaper Module (4.2 inch WeAct, Waveshare-compatible SPI wiring)

This project uses the default SPI/GPIO mapping expected by `waveshare_epd` on Raspberry Pi:

| ePaper Pin | Raspberry Pi Signal | BCM GPIO | Physical Pin |
|---|---|---:|---:|
| VCC | 3.3V power | - | 1 (or 17) |
| GND | Ground | - | 6 (or any GND) |
| DIN | SPI MOSI | GPIO10 | 19 |
| CLK | SPI SCLK | GPIO11 | 23 |
| CS | SPI CE0 | GPIO8 | 24 |
| DC | Data/Command | GPIO25 | 22 |
| RST | Reset | GPIO17 | 11 |
| BUSY | Busy/Ready | GPIO24 | 18 |

Notes:

- Enable SPI on the Pi (`sudo raspi-config` -> Interface Options -> SPI -> Enable).
- Keep button and display grounds common (same GND reference).
- If your specific WeAct board labels or pinout differ, match by signal name (`DIN/CLK/CS/DC/RST/BUSY`) and update driver config only if required by your hardware variant.

## Project Layout

```text
app.py
reader/
  __init__.py
  buttons.py
  display.py
  pagination.py
  storage.py
  web.py
data/
  book.txt
  state.json
requirements.txt
```

## Setup

1. Activate your Raspberry Pi virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Make sure Waveshare ePaper Python driver files are installed and importable so this works:

   ```python
   from waveshare_epd import epd4in2_V2
   ```

## Run

```bash
python app.py
```

The web server starts on `0.0.0.0:8000` by default.

Environment variables:

- `EPAPER_READER_HOST` (default `0.0.0.0`)
- `EPAPER_READER_PORT` (default `8000`)
- `LOG_LEVEL` (default `INFO`)
- `EPAPER_FULL_REFRESH_INTERVAL` (default `4`, minimum `1`)
- `EPAPER_SLEEP_BETWEEN_UPDATES` (default `false`; set `true` for lower idle power, slower turns)

## Web Endpoints

- `GET /` - upload page and current reading status
- `POST /upload` - accepts `.txt` upload only

## Notes

- Uploading a new `.txt` file overwrites `data/book.txt`, resets page to `0`, saves state, and renders the first page.
- If hardware drivers are unavailable, the app still runs and writes a render preview to `data/last_render.png`.
- Page turns prefer partial/fast updates when the driver exposes them, and trigger a full refresh every `EPAPER_FULL_REFRESH_INTERVAL` turns to limit ghosting.

## Troubleshooting

### `No module named 'waveshare_epd'`

Install the official Waveshare Python module and copy it into this project:

```bash
cd /home/raspi
git clone https://github.com/waveshareteam/e-Paper.git
cp -r /home/raspi/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd /home/raspi/book/
```

Then verify:

```bash
cd /home/raspi/book
python3 -c "from waveshare_epd import epd4in2_V2; print('ok')"
```

### `RuntimeError: Failed to add edge detection`

- This can happen on some Raspberry Pi OS/kernel combinations with `RPi.GPIO`.
- The app now auto-falls back to polling mode if edge detection fails.
- Ensure the runtime user has GPIO access:

```bash
sudo usermod -aG gpio raspi
```

Log out and reboot after changing groups.

### Upload or startup appears hung on large books

The app logs progress for pagination and render steps. Follow logs to see where time is spent:

```bash
journalctl -u epaper-reader -f
```

Look for messages like:

- `Paginating book (...)`
- `Pagination complete: ...`
- `Sending full refresh frame to ePaper display.`
- `Sending partial refresh frame to ePaper display.`
- `ePaper update complete.`
