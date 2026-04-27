from __future__ import annotations

from typing import Protocol

from flask import Flask, Response, render_template_string, request

HOME_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ePaper Reader Upload</title>
  </head>
  <body>
    <h1>Raspberry Pi ePaper Reader</h1>
    {% if message %}
    <p style="color: #0a5f0a;">{{ message }}</p>
    {% endif %}
    {% if error %}
    <p style="color: #8b0000;">{{ error }}</p>
    {% endif %}

    <p>Book file: <strong>{{ status.book_file }}</strong></p>
    <p>Current page: <strong>{{ status.current_page + 1 }}</strong> / {{ status.total_pages }}</p>

    <form action="/upload" method="post" enctype="multipart/form-data">
      <label for="book_file">Text file</label>
      <input id="book_file" name="book_file" type="file" accept=".txt,text/plain" required />
      <button type="submit">Upload</button>
    </form>
  </body>
</html>
"""


class ReaderInterface(Protocol):
    def replace_book(self, payload: bytes) -> None:
        pass

    def get_status(self) -> dict:
        pass


def create_web_app(reader: ReaderInterface) -> Flask:
    app = Flask(__name__)

    def render_home(
        message: str | None = None,
        error: str | None = None,
        status_code: int = 200,
    ) -> Response:
        html = render_template_string(
            HOME_TEMPLATE,
            message=message,
            error=error,
            status=reader.get_status(),
        )
        return Response(html, status=status_code, mimetype="text/html")

    @app.get("/")
    def home() -> Response:
        return render_home()

    @app.post("/upload")
    def upload() -> Response:
        uploaded = request.files.get("book_file")
        if uploaded is None or uploaded.filename is None or uploaded.filename == "":
            return render_home(error="No file selected.", status_code=400)

        if not uploaded.filename.lower().endswith(".txt"):
            return render_home(error="Only .txt files are allowed.", status_code=400)

        payload = uploaded.read()
        if payload is None:
            return render_home(error="Failed to read uploaded file.", status_code=400)

        reader.replace_book(payload)
        return render_home(message="Upload complete. Reading restarted from page 1.")

    return app
