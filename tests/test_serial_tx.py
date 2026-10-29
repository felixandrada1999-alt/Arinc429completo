from unittest.mock import patch

import app.serial_tx as serial_tx


def test_send_word_keeps_serial_open_for_repeated_arduino_words() -> None:
    serial_tx._close_serial_device()
    with patch("app.serial_tx.serial.Serial") as serial_constructor, patch(
        "app.serial_tx.sleep"
    ) as boot_delay:
        device = serial_constructor.return_value
        device.is_open = True
        device.write.return_value = 4

        assert serial_tx.send_word("/dev/ttyACM0", 115200, 0x12345678) == 4
        assert serial_tx.send_word("/dev/ttyACM0", 115200, 0x12345678) == 4

        serial_constructor.assert_called_once_with(
            "/dev/ttyACM0", baudrate=115200, timeout=1, write_timeout=1
        )
        boot_delay.assert_called_once_with(serial_tx._ARDUINO_BOOT_DELAY_SECONDS)
        assert device.write.call_count == 2
        assert device.write.call_args.args[0] == bytes((0x78, 0x56, 0x34, 0x12))
        assert device.flush.call_count == 2

    serial_tx._close_serial_device()
