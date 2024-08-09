from datetime import time
from enum import IntEnum
from pydantic import BaseModel


class DayOfWeek(IntEnum):
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6


class Settings(BaseModel):
    beep_dbfs: int = -3
    beep_frequency: int = 1000
    beep_long: float = 1.0
    beep_short: float = 0.5
    day_end: DayOfWeek = DayOfWeek.Sunday
    day_start: DayOfWeek = DayOfWeek.Sunday
    input_device: str = ""
    output_device: str = ""
    time_end: time = time(20, 59, 53)
    time_start: time = time(19, 2, 1)
