from pydantic import BaseModel


class Settings(BaseModel):
    beep_long: float = 1.0
    beep_short: float = 0.5
    input_device: str = ""
    output_device: str = ""
