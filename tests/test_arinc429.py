import pytest

from app.arinc429 import encode_bnr, odd_parity_ok, reverse_label


def test_label_is_reversed_for_arinc_wire_order() -> None:
    assert reverse_label(0o203) == int(f"{0o203:08b}"[::-1], 2)


def test_encoder_builds_32_bit_odd_parity_word() -> None:
    encoded = encode_bnr(50.0, 100.0, label=0o203)

    assert 0 <= encoded.word <= 0xFFFFFFFF
    assert encoded.data_magnitude == round(0.5 * ((1 << 18) - 1))
    assert odd_parity_ok(encoded.word)
    assert encoded.hex == f"0x{encoded.word:08X}"


def test_negative_value_sets_sign_and_negative_ssm() -> None:
    encoded = encode_bnr(-25.0, 100.0, label=0o204)

    assert encoded.negative is True
    assert (encoded.word >> 28) & 1 == 1
    assert (encoded.word >> 29) & 0b11 == 0b11
    assert odd_parity_ok(encoded.word)


@pytest.mark.parametrize("value,scale,label,sdi", [(101, 100, 1, 0), (1, 100, 256, 0), (1, 100, 1, 4), (1, 0, 1, 0)])
def test_invalid_encoder_inputs_raise(value: float, scale: float, label: int, sdi: int) -> None:
    with pytest.raises(ValueError):
        encode_bnr(value, scale, label, sdi)
