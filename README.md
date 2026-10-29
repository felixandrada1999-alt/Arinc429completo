# Gestor de envíos ARINC 429

Aplicación didáctica en español para seleccionar un instrumento, ingresar un valor y crear/consultar/editar/eliminar envíos. Cada registro persiste en MySQL y guarda una palabra de 32 bits según el perfil BNR de ejemplo. La interfaz incluye una vista previa de tono generada por el navegador; no se presenta como tensión analógica calibrada.

## Requisitos y arranque

- Python 3.11 o posterior.
- Docker Compose para MySQL (o una instancia MySQL compatible).

Copia `.env.example` a `.env`, crea un entorno virtual e instala `requirements.txt`. Inicia la base con `docker compose up -d mysql` y luego ejecuta `uvicorn app.main:app --reload`. La interfaz queda en `http://127.0.0.1:8000` y la documentación HTTP en `/docs`.

**Abrir el CRUD:** [http://127.0.0.1:8000](http://127.0.0.1:8000). Este enlace funciona cuando el servidor está iniciado en tu equipo.

### Publicarlo para abrirlo desde Internet

GitHub aloja el código, pero no ejecuta esta aplicación FastAPI ni su base de datos. Por eso, abrir el repositorio o activar GitHub Pages no abre el CRUD. Para tener una URL pública, publica el servicio en Render desde este repositorio: crea un Blueprint y selecciona `render.yaml`. El Blueprint configura la aplicación y una base PostgreSQL; al terminar, Render mostrará una URL HTTPS para abrir el CRUD. Mantén `SERIAL_ENABLED=false` en la nube: el servicio alojado no tiene acceso al puerto serie de tu equipo. La base PostgreSQL gratuita, si está disponible en tu cuenta/región, puede tener límites o caducar según el plan de Render.

También puedes probar localmente sin Docker/MySQL estableciendo `DATABASE_URL=sqlite:///./arinc429.db` antes de iniciar Uvicorn. Para datos persistentes de producción, usa una base administrada; el disco local de los alojamientos gratuitos puede ser efímero.

La aplicación crea las tablas y agrega tres instrumentos de ejemplo al iniciar. Con `SERIAL_ENABLED=false`, crear un envío solo lo guarda; la transmisión queda desactivada. Con `SERIAL_ENABLED=true`, crear intenta enviar automáticamente la palabra al UART configurado y solo registra el envío si la escritura serial termina correctamente. El endpoint de retransmisión también requiere esa opción y un adaptador de laboratorio compatible.

## Receptor Arduino

El firmware para Arduino Uno/Nano con LCD 16x2 I2C está en [arduino/receiver](arduino/receiver/README.md). Valida paridad, etiqueta, signo y SSM, muestra instrumento/valor y representa cada bit con salidas lógicas en los pines 13 y 12. Para probarlo, configura `SERIAL_ENABLED=true` y `SERIAL_PORT` con el dispositivo serie Arduino; el backend conserva el puerto abierto para evitar el reinicio USB entre envíos. No conectes esas salidas directamente a un bus ARINC 429 ni a cargas de potencia.

## API

- `GET /api/instruments`: instrumentos y límites.
- `GET /api/shipments`: lista de envíos.
- `POST /api/shipments` con `{"instrument_id": 1, "value": 42.5}`: crea un envío y calcula la palabra; además transmite por UART si `SERIAL_ENABLED=true`.
- `PUT /api/shipments/{id}`: modifica el instrumento/valor y regenera la palabra.
- `DELETE /api/shipments/{id}`: elimina el envío.
- `POST /api/shipments/{id}/transmit`: envía explícitamente los cuatro bytes al UART configurado solo si hardware está habilitado.

La tabla `shipments` conserva instrumento, valor, palabra y marcas de tiempo; `instruments` define etiqueta, unidad y rango. Las ediciones limpian `transmitted_at` porque la palabra guardada cambia.

## Perfil de palabra de demostración

El codificador usa etiqueta invertida para el orden de transmisión ARINC, SDI=0, magnitud de 18 bits, signo en bit 29 (numeración ARINC desde 1), SSM de 2 bits con `00` para positivo y `11` para negativo, y paridad impar en bit 32. El campo cuantizado usa `abs(valor) / escala_completa`, donde escala completa es el máximo absoluto del rango del instrumento. Los valores fuera del rango se rechazan.

**Este es un perfil ilustrativo, no una codificación interoperable sin ICD.** Una integración real debe definir para cada etiqueta: formato (BNR/BCD/discrete), resolución/unidades, SDI, escalado, codificación del signo y SSM, orden de transmisión y temporización. Confirmar también la convención del campo con el equipo receptor.

La rutina de puerto serie usa UART y orden de bytes little-endian para un adaptador de laboratorio definido por el usuario. UART no equivale a ARINC 429: no conectar UART/GPIO ni la salida de auricular al bus. Para un bus real se necesita transmisor/receptor ARINC429 apropiado con niveles diferenciales, aislamiento y protección diseñados según el sistema.

La interfaz genera un tono de 440 Hz cuyo nivel relativo varía linealmente con el valor dentro del rango del instrumento. Ese audio se reproduce en la salida seleccionada del navegador; no se puede prometer un voltaje físico específico, ya que depende del DAC, volumen, auricular y carga. No es una salida analógica calibrada ni sustituye un DAC/etapa de salida diseñada y medida.

## Auricular y servo

Ver [docs/circuito-servo.md](docs/circuito-servo.md). El circuito recomendado es de alta impedancia, con acoplamiento AC, buffer, detección/ADC, firmware con límites y salida PWM. La salida de auricular solo debe usarse con la etapa analógica adecuada y verificada. Nunca alimentar un servo desde el jack o el ADC directamente.

## Pruebas

Ejecuta `pytest`. Las pruebas usan SQLite en memoria; no requieren conectar MySQL, puerto serie, auricular ni servo.
