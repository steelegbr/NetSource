from pydantic import BaseModel


class Settings(BaseModel):
    input_device: str = ""
    output_device: str = ""
