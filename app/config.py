from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://arinc:arinc_dev_only@localhost:3307/arinc429?charset=utf8mb4"
    serial_enabled: bool = False
    serial_port: str = "/dev/ttyUSB0"
    serial_baudrate: int = 115200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
