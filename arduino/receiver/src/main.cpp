#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Servo.h>

namespace {
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint8_t ONE_PIN = 13;
constexpr uint8_t ZERO_PIN = 12;
constexpr uint8_t SERVO_PIN = 9;
// Adjust and mechanically test these limits for the specific servo/linkage.
constexpr uint8_t SERVO_MIN_DEGREES = 20;
constexpr uint8_t SERVO_MAX_DEGREES = 160;
constexpr uint16_t BIT_PULSE_MS = 10;
constexpr uint16_t INPUT_TIMEOUT_MS = 250;
constexpr uint32_t DATA_MAX = (1UL << 18) - 1;

// Common I2C LCD address is 0x27. Change to 0x3F if that is the module's address.
LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo servo;
uint8_t rxBytes[4] = {0, 0, 0, 0};
uint8_t rxCount = 0;
uint32_t lastByteAt = 0;

struct Instrument {
  const char *name;
  const char *unit;
  uint8_t label;
  float minValue;
  float maxValue;
  float fullScale;
};

const Instrument instruments[] = {
    {"Temperatura", "C", 0203, -100.0F, 100.0F, 100.0F},
    {"Presion", "kPa", 0204, 0.0F, 500.0F, 500.0F},
    {"Altitud", "ft", 0210, -1000.0F, 60000.0F, 60000.0F},
};

uint8_t reverseBits(uint8_t value) {
  uint8_t reversed = 0;
  for (uint8_t bit = 0; bit < 8; ++bit) {
    reversed = static_cast<uint8_t>((reversed << 1) | (value & 1U));
    value >>= 1;
  }
  return reversed;
}

const Instrument *findInstrument(uint8_t encodedLabel) {
  const uint8_t label = reverseBits(encodedLabel);
  for (const Instrument &instrument : instruments) {
    if (instrument.label == label) {
      return &instrument;
    }
  }
  return nullptr;
}

void showMessage(const char *line1, const char *line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

void outputWordBits(uint32_t word) {
  // Reproduce received UART byte order: little-endian bytes, LSB first per byte.
  // HIGH is placed on pin 13 for a 1 and on pin 12 for a 0.
  for (uint8_t bit = 0; bit < 32; ++bit) {
    const bool isOne = ((word >> bit) & 1UL) != 0;
    digitalWrite(ONE_PIN, isOne ? HIGH : LOW);
    digitalWrite(ZERO_PIN, isOne ? LOW : HIGH);
    delay(BIT_PULSE_MS);
  }
  digitalWrite(ONE_PIN, LOW);
  digitalWrite(ZERO_PIN, LOW);
}

bool decodeWord(uint32_t word, const Instrument *&instrument, float &value) {
  uint32_t parityBits = word;
  bool oddParity = false;
  while (parityBits != 0) {
    oddParity = oddParity != ((parityBits & 1UL) != 0);
    parityBits >>= 1;
  }
  if (!oddParity) {
    return false; // This demo profile requires odd parity across all 32 bits.
  }

  instrument = findInstrument(static_cast<uint8_t>(word & 0xFFU));
  if (instrument == nullptr) {
    return false; // Unknown ARINC label.
  }

  const bool negative = ((word >> 28) & 1UL) != 0;
  const uint8_t ssm = static_cast<uint8_t>((word >> 29) & 0x03U);
  if ((!negative && ssm != 0b00) || (negative && ssm != 0b11)) {
    return false; // Reject inconsistent sign/status combinations.
  }

  const uint32_t magnitude = (word >> 10) & DATA_MAX;
  value = (static_cast<float>(magnitude) / static_cast<float>(DATA_MAX)) * instrument->fullScale;
  if (negative) {
    value = -value;
  }
  if (value < instrument->minValue || value > instrument->maxValue) {
    return false;
  }
  return true;
}

void setServoFromValue(float value, const Instrument &instrument) {
  const float normalized = (value - instrument.minValue) /
                           (instrument.maxValue - instrument.minValue);
  const float bounded = constrain(normalized, 0.0F, 1.0F);
  const uint8_t degrees = static_cast<uint8_t>(
      SERVO_MIN_DEGREES + bounded * (SERVO_MAX_DEGREES - SERVO_MIN_DEGREES) + 0.5F);
  servo.write(degrees);
}

void handleCandidate() {
  const uint32_t word = static_cast<uint32_t>(rxBytes[0]) |
                        (static_cast<uint32_t>(rxBytes[1]) << 8) |
                        (static_cast<uint32_t>(rxBytes[2]) << 16) |
                        (static_cast<uint32_t>(rxBytes[3]) << 24);

  const Instrument *instrument = nullptr;
  float value = 0.0F;
  if (decodeWord(word, instrument, value)) {
    char valueLine[17];
    char valueText[12];
    // Keep the text within the 16-character LCD row.
    dtostrf(value, 0, 1, valueText);
    snprintf(valueLine, sizeof(valueLine), "%s %s", valueText, instrument->unit);
    showMessage(instrument->name, valueLine);
    setServoFromValue(value, *instrument);
    rxCount = 0;
    outputWordBits(word);
    return;
  }

  // Slide one byte at a time to recover alignment if serial reception started
  // in the middle of a 4-byte word.
  for (uint8_t i = 0; i < 3; ++i) {
    rxBytes[i] = rxBytes[i + 1];
  }
  rxCount = 3;
}
} // namespace

void setup() {
  pinMode(ONE_PIN, OUTPUT);
  pinMode(ZERO_PIN, OUTPUT);
  servo.attach(SERVO_PIN);
  servo.write(SERVO_MIN_DEGREES);
  digitalWrite(ONE_PIN, LOW);
  digitalWrite(ZERO_PIN, LOW);

  Serial.begin(SERIAL_BAUD);
  lcd.init();
  lcd.backlight();
  showMessage("ARINC 429 listo", "Esperando datos");
}

void loop() {
  while (Serial.available() > 0) {
    const uint8_t incoming = static_cast<uint8_t>(Serial.read());
    lastByteAt = millis();

    if (rxCount < 4) {
      rxBytes[rxCount++] = incoming;
    }
    if (rxCount == 4) {
      handleCandidate();
    }
  }

  if (rxCount > 0 && millis() - lastByteAt > INPUT_TIMEOUT_MS) {
    rxCount = 0;
    showMessage("Dato no valido", "Parity/label/SSM");
  }
}
