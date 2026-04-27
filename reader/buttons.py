from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict

LOGGER = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None

Callback = Callable[[], None]


@dataclass
class ButtonController:
    on_previous: Callback
    on_next: Callback
    previous_pin: int = 27
    next_pin: int = 22
    debounce_seconds: float = 0.2
    poll_interval_seconds: float = 0.03
    _last_press: Dict[int, float] = field(default_factory=dict, init=False)
    _started: bool = field(default=False, init=False)
    _using_edge_detect: bool = field(default=False, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _poll_thread: threading.Thread | None = field(default=None, init=False)
    _last_pin_state: Dict[int, int] = field(default_factory=dict, init=False)

    def start(self) -> None:
        if GPIO is None:
            LOGGER.warning("RPi.GPIO not available; button input disabled.")
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.previous_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.next_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        try:
            GPIO.add_event_detect(
                self.previous_pin,
                GPIO.FALLING,
                callback=self._handle_previous,
                bouncetime=int(self.debounce_seconds * 1000),
            )
            GPIO.add_event_detect(
                self.next_pin,
                GPIO.FALLING,
                callback=self._handle_next,
                bouncetime=int(self.debounce_seconds * 1000),
            )
            self._using_edge_detect = True
            LOGGER.info(
                "Buttons initialized with edge detection (previous GPIO%s, next GPIO%s).",
                self.previous_pin,
                self.next_pin,
            )
        except RuntimeError as exc:
            self._remove_event_handlers()
            self._start_polling_mode()
            LOGGER.warning(
                "Edge detection unavailable (%s). Falling back to polling mode.",
                exc,
            )

        self._started = True

    def _is_debounced(self, pin: int) -> bool:
        now = time.monotonic()
        last = self._last_press.get(pin, 0.0)
        if (now - last) < self.debounce_seconds:
            return False
        self._last_press[pin] = now
        return True

    def _handle_previous(self, _: int) -> None:
        if not self._is_debounced(self.previous_pin):
            return
        self._run_previous_action()

    def _handle_next(self, _: int) -> None:
        if not self._is_debounced(self.next_pin):
            return
        self._run_next_action()

    def _run_previous_action(self) -> None:
        try:
            self.on_previous()
        except Exception:
            LOGGER.exception("Error handling previous-page button press.")

    def _run_next_action(self) -> None:
        try:
            self.on_next()
        except Exception:
            LOGGER.exception("Error handling next-page button press.")

    def _start_polling_mode(self) -> None:
        self._using_edge_detect = False
        self._stop_event.clear()
        self._last_pin_state = {
            self.previous_pin: GPIO.input(self.previous_pin),
            self.next_pin: GPIO.input(self.next_pin),
        }
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="button-poll",
            daemon=True,
        )
        self._poll_thread.start()
        LOGGER.info(
            "Buttons initialized with polling (interval %.3fs).",
            self.poll_interval_seconds,
        )

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            for pin, callback in (
                (self.previous_pin, self._run_previous_action),
                (self.next_pin, self._run_next_action),
            ):
                current = GPIO.input(pin)
                last = self._last_pin_state.get(pin, GPIO.HIGH)
                if last == GPIO.HIGH and current == GPIO.LOW and self._is_debounced(pin):
                    callback()
                self._last_pin_state[pin] = current
            time.sleep(self.poll_interval_seconds)

    def _remove_event_handlers(self) -> None:
        if GPIO is None:
            return
        for pin in (self.previous_pin, self.next_pin):
            try:
                GPIO.remove_event_detect(pin)
            except RuntimeError:
                pass

    def cleanup(self) -> None:
        if GPIO is None or not self._started:
            return

        if self._using_edge_detect:
            self._remove_event_handlers()
        else:
            self._stop_event.set()
            if self._poll_thread is not None:
                self._poll_thread.join(timeout=1.0)
                self._poll_thread = None

        GPIO.cleanup((self.previous_pin, self.next_pin))
        self._started = False
