"""Encoder del perfil BNR de magnitud/signo usado por esta demo.

La etiqueta se invierte para el orden de transmisión ARINC habitual. Confirme
siempre etiqueta, SDI, escala, SSM, paridad y orden de bits contra el ICD real.
"""

from dataclasses import dataclass

DATA_MAX = (1 << 18) - 1


@dataclass(frozen=True)
class EncodedWord:
    word: int
    data_magnitude: int
    negative: bool

    @property
    def hex(self) -> str:
        return f"0x{self.word:08X}"


def reverse_label(label: int) -> int:
    if not 0 <= label <= 0xFF:
        raise ValueError("La etiqueta debe estar entre 0 y 255")
    return int(f"{label:08b}"[::-1], 2)


def encode_bnr(value: float, full_scale: float, label: int, sdi: int = 0) -> EncodedWord:
    """Empaqueta label, SDI, magnitud de 18 bits, signo, SSM y paridad impar.

    El valor se satura únicamente por validación: valores fuera de escala fallan.
    Para este perfil SSM=00 representa positivo y SSM=11 negativo.
    """
    if full_scale <= 0:
        raise ValueError("La escala completa debe ser positiva")
    if abs(value) > full_scale:
        raise ValueError("El valor excede la escala completa del instrumento")
    if not 0 <= sdi <= 3:
        raise ValueError("SDI debe estar entre 0 y 3")

    negative = value < 0
    magnitude = round(abs(value) / full_scale * DATA_MAX)
    word = reverse_label(label)
    word |= sdi << 8
    word |= magnitude << 10
    word |= int(negative) << 28
    word |= (0b11 if negative else 0b00) << 29

    # Bit 32 (índice 31) completa paridad impar sobre los 32 bits.
    if word.bit_count() % 2 == 0:
        word |= 1 << 31

    return EncodedWord(word=word, data_magnitude=magnitude, negative=negative)


def odd_parity_ok(word: int) -> bool:
    return 0 <= word <= 0xFFFFFFFF and word.bit_count() % 2 == 1
