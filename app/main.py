from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
import serial

from app.arinc429 import encode_bnr
from app.config import settings
from app.database import Base, build_engine
from app.models import Instrument, Shipment
from app.schemas import InstrumentRead, ShipmentRead, ShipmentWrite
from app.serial_tx import send_word

DEFAULT_INSTRUMENTS = (
    {"name": "Temperatura", "label": 0o203, "unit": "°C", "min_value": -100.0, "max_value": 100.0},
    {"name": "Presión", "label": 0o204, "unit": "kPa", "min_value": 0.0, "max_value": 500.0},
    {"name": "Altitud", "label": 0o210, "unit": "ft", "min_value": -1000.0, "max_value": 60000.0},
)
STATIC_DIR = Path(__file__).parent / "static"


def create_app(engine: Engine | None = None, serial_enabled: bool | None = None) -> FastAPI:
    db_engine = engine or build_engine(settings.database_url)
    session_factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    hardware_enabled = settings.serial_enabled if serial_enabled is None else serial_enabled

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=db_engine)
        with session_factory() as db:
            for values in DEFAULT_INSTRUMENTS:
                exists = db.scalar(select(Instrument).where(Instrument.name == values["name"]))
                if exists is None:
                    db.add(Instrument(**values))
            db.commit()
        yield
        if engine is None:
            db_engine.dispose()

    app = FastAPI(title="Gestor de envíos ARINC 429", version="1.0.0", lifespan=lifespan)
    app.state.serial_enabled = hardware_enabled
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def get_db() -> Iterator[Session]:
        with session_factory() as db:
            yield db

    def find_instrument(db: Session, instrument_id: int) -> Instrument:
        instrument = db.get(Instrument, instrument_id)
        if instrument is None:
            raise HTTPException(status_code=404, detail="Instrumento no encontrado")
        return instrument

    def find_shipment(db: Session, shipment_id: int) -> Shipment:
        shipment = db.get(Shipment, shipment_id)
        if shipment is None:
            raise HTTPException(status_code=404, detail="Envío no encontrado")
        return shipment

    def validate_value(instrument: Instrument, value: float) -> None:
        if not instrument.min_value <= value <= instrument.max_value:
            raise HTTPException(
                status_code=422,
                detail=f"El valor debe estar entre {instrument.min_value} y {instrument.max_value} {instrument.unit}",
            )

    def make_shipment_read(shipment: Shipment) -> ShipmentRead:
        return ShipmentRead(
            id=shipment.id,
            instrument_id=shipment.instrument_id,
            instrument_name=shipment.instrument.name,
            unit=shipment.instrument.unit,
            value=shipment.value,
            min_value=shipment.instrument.min_value,
            max_value=shipment.instrument.max_value,
            arinc_word=shipment.arinc_word,
            arinc_hex=f"0x{shipment.arinc_word:08X}",
            created_at=shipment.created_at,
            transmitted_at=shipment.transmitted_at,
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "serial_enabled": hardware_enabled}

    @app.get("/api/instruments", response_model=list[InstrumentRead])
    def list_instruments(db: Session = Depends(get_db)) -> list[Instrument]:
        return list(db.scalars(select(Instrument).order_by(Instrument.id)).all())

    @app.get("/api/shipments", response_model=list[ShipmentRead])
    def list_shipments(db: Session = Depends(get_db)) -> list[ShipmentRead]:
        shipments = db.scalars(select(Shipment).order_by(Shipment.id.desc())).all()
        return [make_shipment_read(item) for item in shipments]

    @app.post("/api/shipments", response_model=ShipmentRead, status_code=status.HTTP_201_CREATED)
    def create_shipment(payload: ShipmentWrite, db: Session = Depends(get_db)) -> ShipmentRead:
        instrument = find_instrument(db, payload.instrument_id)
        validate_value(instrument, payload.value)
        full_scale = max(abs(instrument.min_value), abs(instrument.max_value))
        encoded = encode_bnr(payload.value, full_scale, instrument.label)
        transmitted_at = None
        if hardware_enabled:
            try:
                send_word(settings.serial_port, settings.serial_baudrate, encoded.word)
            except (serial.SerialException, OSError, ValueError) as exc:
                raise HTTPException(status_code=502, detail=f"No se pudo enviar al puerto serie: {exc}") from exc
            transmitted_at = datetime.now(timezone.utc)
        shipment = Shipment(
            instrument=instrument,
            value=payload.value,
            arinc_word=encoded.word,
            transmitted_at=transmitted_at,
        )
        db.add(shipment)
        db.commit()
        db.refresh(shipment)
        return make_shipment_read(shipment)

    @app.put("/api/shipments/{shipment_id}", response_model=ShipmentRead)
    def update_shipment(
        shipment_id: int, payload: ShipmentWrite, db: Session = Depends(get_db)
    ) -> ShipmentRead:
        shipment = find_shipment(db, shipment_id)
        instrument = find_instrument(db, payload.instrument_id)
        validate_value(instrument, payload.value)
        full_scale = max(abs(instrument.min_value), abs(instrument.max_value))
        encoded = encode_bnr(payload.value, full_scale, instrument.label)
        transmitted_at = None
        if hardware_enabled:
            try:
                send_word(settings.serial_port, settings.serial_baudrate, encoded.word)
            except (serial.SerialException, OSError, ValueError) as exc:
                raise HTTPException(status_code=502, detail=f"No se pudo enviar al puerto serie: {exc}") from exc
            transmitted_at = datetime.now(timezone.utc)
        shipment.instrument = instrument
        shipment.value = payload.value
        shipment.arinc_word = encoded.word
        shipment.transmitted_at = transmitted_at
        db.commit()
        db.refresh(shipment)
        return make_shipment_read(shipment)

    @app.delete("/api/shipments/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_shipment(shipment_id: int, db: Session = Depends(get_db)) -> Response:
        shipment = find_shipment(db, shipment_id)
        db.delete(shipment)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/shipments/{shipment_id}/transmit", response_model=ShipmentRead)
    def transmit_shipment(shipment_id: int, db: Session = Depends(get_db)) -> ShipmentRead:
        if not hardware_enabled:
            raise HTTPException(
                status_code=409,
                detail="Transmisión deshabilitada. Configure SERIAL_ENABLED=true y use un adaptador de laboratorio compatible.",
            )
        shipment = find_shipment(db, shipment_id)
        try:
            send_word(settings.serial_port, settings.serial_baudrate, shipment.arinc_word)
        except (serial.SerialException, OSError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"No se pudo enviar al puerto serie: {exc}") from exc
        shipment.transmitted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(shipment)
        return make_shipment_read(shipment)

    return app


app = create_app()
