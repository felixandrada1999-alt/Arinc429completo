# Receptor ARINC de demostración para Arduino

Firmware PlatformIO para **Arduino Uno/Nano ATmega328P** y LCD 16x2 con adaptador I2C. Lee por USB serie el mismo formato que genera `app/serial_tx.py`: cuatro bytes binarios little-endian a 115200 baudios, que contienen una palabra BNR de demostración.

## Comportamiento

- Busca palabras con etiqueta conocida y paridad impar correcta; recupera alineación byte a byte si empieza a escuchar a mitad de una palabra.
- Verifica la combinación de signo y SSM (`00` positivo, `11` negativo) y decodifica etiqueta/escala para Temperatura, Presión o Altitud.
- Muestra instrumento y valor en la pantalla; una palabra inválida muestra un aviso.
- Por cada palabra aceptada, recorre los 32 bits empezando por el bit menos significativo (orden de bytes transmitido): deja el pin 13 en HIGH durante 10 ms para un `1`, o el pin 12 en HIGH durante 10 ms para un `0`; el otro pin queda LOW. Al terminar ambos quedan LOW.

Este es el perfil didáctico de la aplicación, **no una implementación certificada/interoperable ARINC 429**.

## Cableado

- Arduino GND ↔ GND de la interfaz USB-serie / LCD.
- LCD I2C: VCC → 5 V, GND → GND, SDA → A4, SCL → A5 en Uno/Nano.
- Señal lógica `1` → pin digital 13; señal lógica `0` → pin digital 12. Ambos son salidas de 5 V en Uno/Nano. Conectar solo a entradas de alta impedancia compatibles con 5 V o a indicadores con resistencia apropiada; **no** conectar a un bus ARINC 429, servo, auricular ni cargas de potencia. Usar adaptación de nivel/aislamiento si el circuito receptor no tolera 5 V.
- La dirección LCD está configurada como `0x27`; cambiarla a `0x3F` en `src/main.cpp` si el módulo usa esa dirección.
- Conectar el Arduino al mismo ordenador/puerto serie que configura la aplicación (`SERIAL_PORT`, por ejemplo `/dev/ttyACM0` o `/dev/ttyUSB0`). La velocidad debe ser 115200.

## Compilar y cargar

1. Abrir la carpeta `arduino/receiver` en VS Code con PlatformIO.
2. Ejecutar **PlatformIO: Build** y luego **PlatformIO: Upload**. Seleccionar el puerto correcto si PlatformIO lo solicita.
3. La aplicación FastAPI debe ejecutarse en el mismo ordenador con `SERIAL_ENABLED=true` y `SERIAL_PORT` apuntando al Arduino. No abrir simultáneamente el Monitor Serie: el puerto debe quedar disponible para el backend.

El backend mantiene abierto el puerto serial y espera el arranque del Arduino al conectarse, para evitar que el reinicio automático por USB descarte la primera palabra.
