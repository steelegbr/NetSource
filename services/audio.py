from enum import Enum
from pyaudio import (
    paAL,
    paALSA,
    paASIO,
    paBeOS,
    paCoreAudio,
    paDirectSound,
    paInDevelopment,
    paJACK,
    paMME,
    paOSS,
    paSoundManager,
    paWASAPI,
    paWDMKS,
    PyAudio,
)
from pydantic import BaseModel
from services.logging import get_logger, Logger
from typing import List


class AudioEngine(Enum):
    PulseAudio = paAL
    ALSA = paALSA
    ASIO = paASIO
    BeOS = paBeOS
    CoreAudio = paCoreAudio
    DirectSound = paDirectSound
    InDevelopment = paInDevelopment
    JACK = paJACK
    MME = paMME
    OSS = paOSS
    SoundManager = paSoundManager
    WASAPI = paWASAPI
    WDMKS = paWDMKS


class SoundCard(BaseModel):
    engine: AudioEngine
    id: int
    name: str


class AudioService:
    __input_devices: SoundCard
    __instance = None
    __logger: Logger
    __pa: PyAudio

    LOG_PREFIX = "Audio Service"

    def __init__(self) -> None:
        raise RuntimeError(
            "Direct instantiation not permitted, call AudioService.instance() instead"
        )

    @classmethod
    def instance(cls, logger: Logger = get_logger(__name__)):
        if cls.__instance is None:
            cls.__instance = cls.__new__(cls)
            cls.__instance.__logger = logger
            cls.__pa = PyAudio()
        return cls.__instance

    def get_soundcards(self) -> List[SoundCard]:
        device_count = self.__pa.get_device_count()
        self.__logger.info(f"{self.LOG_PREFIX}: found %d device(s)", device_count)

        sound_cards: List[SoundCard] = []

        for i in range(0, device_count):
            current_device = self.__pa.get_device_info_by_index(i)
            if current_device["maxInputChannels"] > 0:
                sound_card = SoundCard(
                    engine=current_device["hostApi"],
                    id=current_device["index"],
                    name=current_device["name"],
                )
                self.__logger.info(
                    f"{self.LOG_PREFIX}: mapped sound card %s", sound_card
                )
                sound_cards.append(sound_card)

        self.__logger.info(
            f"{self.LOG_PREFIX}: found %d recording device(s)", len(sound_cards)
        )
        return sound_cards

    def set_input_device(self, sound_card: SoundCard):
        self.__logger.info(f"{self.LOG_PREFIX}: set input device to %s", sound_card)
        self.__input_device = sound_card
