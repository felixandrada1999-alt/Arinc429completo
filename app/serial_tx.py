import atexit
from threading import Lock
from time import sleep

import serial

_serial_lock = Lock()
_serial_device: serial.Serial | None = None
_serial_config: tuple[str, int] | None = None
_ARDUINO_BOOT_DELAY_SECONDS = 2.0


def _close_serial_device() -> None:
    global _serial_device, _serial_config
    with _serial_lock:
        if _serial_device is not None and _serial_device.is_open:
            _serial_device.close()
        _serial_device = None
        _serial_config = None


atexit.register(_close_serial_device)


def send_word(port: str, baudrate: int, word: int) -> int:
    """Envía 4 bytes a UART y conserva abierto el puerto hasta cerrar el proceso.

    Mantenerlo abierto evita reiniciar el Arduino Uno/Nano por auto-reset USB en
    cada envío. Hace falta un transmisor ARINC429 aislado para un bus real.
    """
    payload = word.to_bytes(4, byteorder="little", signed=False)
    global _serial_device, _serial_config
    with _serial_lock:
        config = (port, baudrate)
        if _serial_device is None or not _serial_device.is_open or _serial_config != config:
            _close_current_device()
            _serial_device = serial.Serial(port, baudrate=baudrate, timeout=1, write_timeout=1)
            _serial_config = config
            # Opening USB serial commonly resets Uno/Nano; wait through bootloader.
            sleep(_ARDUINO_BOOT_DELAY_SECONDS)

        try:
            written = _serial_device.write(payload)
            _serial_device.flush()
        except (serial.SerialException, OSError):
            _close_current_device()
            raise

        if written != len(payload):
            _close_current_device()
            raise IOError(f"Transmisión incompleta: {written}/{len(payload)} bytes")
        return written


def _close_current_device() -> None:
    global _serial_device, _serial_config
    if _serial_device is not None and _serial_device.is_open:
        _serial_device.close()
    _serial_device = None
    _serial_config = None
