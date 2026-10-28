import serial


def send_word(port: str, baudrate: int, word: int) -> int:
    """Envía los 4 bytes a un puerto UART de laboratorio, no a un bus ARINC.

    Hace falta un transmisor ARINC429 certificado/aislado entre UART y el bus.
    """
    payload = word.to_bytes(4, byteorder="little", signed=False)
    with serial.Serial(port, baudrate=baudrate, timeout=1, write_timeout=1) as device:
        written = device.write(payload)
        device.flush()
    if written != len(payload):
        raise IOError(f"Transmisión incompleta: {written}/{len(payload)} bytes")
    return written
