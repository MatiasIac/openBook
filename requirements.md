# Raspberry Pi ePaper Reader Requirements

## Overview

Build a small Python application for a Raspberry Pi Zero 2 W connected to a WeAct 4.2 inch ePaper display. The app will display a plain text book and allow the user to move backward and forward through pages using two physical buttons.

## Hardware

The application must use:

* Raspberry Pi Zero 2 W
* WeAct 4.2 inch ePaper display
* Waveshare-compatible V2 driver:

```python
from waveshare_epd import epd4in2_V2
```

* Two physical buttons:

  * Previous page: GPIO27, physical pin 13
  * Next page: GPIO22, physical pin 15
* Buttons are wired to GND and should use internal pull-up resistors.

## Functional Requirements

### Display

* Use the configured 4.2 inch ePaper display.
* Render text pages clearly on the display.
* Use the `epd4in2_V2` driver.
* The screen should show one page of text at a time.
* After rendering, the display should be put into sleep mode where appropriate.

### Navigation

* Pressing the forward button moves to the next page.
* Pressing the back button moves to the previous page.
* Page number must not go below the first page.
* Page number must not go beyond the final page.
* Button presses should be debounced in software.

### Book Storage

* The app supports only one book at a time.
* Uploaded books must be plain `.txt` files only.
* If a new book is uploaded, it replaces the existing book.
* When a new book is uploaded:

  * The current page is reset to page `0`.
  * The new book is displayed from the beginning.

### Reading Progress

* The current page must be saved locally.
* When the Raspberry Pi restarts, the app must resume from the last page read.
* Progress should be stored in a simple local file, such as `state.json`.

Example:

```json
{
  "current_page": 12,
  "book_file": "book.txt"
}
```

### Upload Endpoint

* The application must run a small local web server.
* It must expose a `POST` endpoint for uploading a text file.
* It must also serve a simple HTML page with:

  * A file upload input
  * An upload button

Suggested routes:

```text
GET  /
POST /upload
```

### Upload Rules

* Only `.txt` files are accepted.
* If another file type is uploaded, return an error message.
* Uploaded file should replace the current book.
* After upload, reset reading progress to the beginning.
* After upload, render page `0` on the ePaper display.

## Suggested Project Structure

```text
epaper-reader/
  app.py
  reader/
    display.py
    buttons.py
    pagination.py
    storage.py
    web.py
  data/
    book.txt
    state.json
  requirements.txt
  README.md
```

## Suggested Python Dependencies

```text
flask
Pillow
RPi.GPIO
spidev
```

The application should run inside the existing Raspberry Pi Python virtual environment.

## Non-Goals for Now

Do not implement:

* Multiple book library
* PDF, EPUB, DOCX, or Markdown support
* Wi-Fi setup UI
* User accounts
* Styling-heavy web interface
* Touchscreen support
* Battery monitoring
* Book metadata

## Success Criteria

The app is working when:

1. A `.txt` file can be uploaded from a browser.
2. The first page appears on the ePaper display.
3. The next button moves forward one page.
4. The back button moves backward one page.
5. The current page is saved.
6. Restarting the app resumes from the last page read.
7. Uploading a new book replaces the old book and starts from page `0`.
