import numpy as np
from enum import Enum, StrEnum
from math import log10, sqrt
from pyaudio import (
    Stream,
    paAL,
    paALSA,
    paASIO,
    paBeOS,
    paContinue,
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
from typing import Callable, Dict, List


class AudioEngineState(StrEnum):
    Stopped = "STOP"
    Started = "START"
    Error = "ERROR"


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
    channels: int
    engine: AudioEngine
    id: int
    name: str


class AudioService:
    __input_device: SoundCard
    __instance = None
    __level_callbacks: List[Callable[[float, float], None]]
    __logger: Logger
    __pa: PyAudio
    __state: AudioEngineState
    __stream: Stream

    LOG_PREFIX = "Audio Service"
    MAX_CHANNELS = 2
    SAMPLE_RATE = 48000
    WORD_SIZE = 2

    def __init__(self) -> None:
        raise RuntimeError(
            "Direct instantiation not permitted, call AudioService.instance() instead"
        )

    @classmethod
    def instance(cls, logger: Logger = get_logger(__name__)):
        if cls.__instance is None:
            cls.__instance = cls.__new__(cls)
            cls.__instance.__input_device = None
            cls.__instance.__level_callbacks = []
            cls.__instance.__logger = logger
            cls.__pa = PyAudio()
            cls.__state = AudioEngineState.Stopped
        return cls.__instance

    def get_soundcards(self) -> List[SoundCard]:
        device_count = self.__pa.get_device_count()
        self.__logger.info(f"{self.LOG_PREFIX}: found %d device(s)", device_count)

        sound_cards: List[SoundCard] = []

        for i in range(0, device_count):
            current_device = self.__pa.get_device_info_by_index(i)
            if current_device["maxInputChannels"] > 0:
                sound_card = SoundCard(
                    channels=current_device["maxInputChannels"],
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
        if not self.__input_device == sound_card:
            if self.__state == AudioEngineState.Started:
                self.stop()
            self.__input_device = sound_card
            self.start()

    def stop(self):
        self.__logger.info(f"{self.LOG_PREFIX}: stop audio engine")
        if self.__stream:
            self.__stream.stop_stream()
            self.__stream.close()
            self.__stream = None

    def start(self):
        self.__logger.info(
            f"{self.LOG_PREFIX}: start audio engine on devices %s", self.__input_device
        )
        self.__stream = self.__pa.open(
            self.SAMPLE_RATE,
            self.__calculate_channel_count(),
            self.__pa.get_format_from_width(self.WORD_SIZE),
            True,
            False,
            self.__input_device.id,
            stream_callback=self.__record_callback,
        )
        self.__state = AudioEngineState.Started

    def __calculate_channel_count(self) -> int:
        return min(self.__input_device.channels, self.MAX_CHANNELS)

    def __calculate_numpy_type(self):
        if self.WORD_SIZE == 2:
            return np.int16
        return np.int8

    def __record_callback(
        self, in_data: bytes, frame_count: int, time_info: Dict, status
    ):
        self.__calculate_levels(in_data, frame_count)
        return (in_data, paContinue)

    def __calculate_levels(self, in_data: bytes, frame_count: int):
        # Decode and deinterleve

        frames = np.frombuffer(in_data, self.__calculate_numpy_type())
        deinterleaved = [
            frames[idx :: self.__calculate_channel_count()]
            for idx in range(self.__calculate_channel_count())
        ]

        # Calculate a VU number
        # We force stereo

        power_left = np.square(deinterleaved[0], dtype=np.int64)
        if len(deinterleaved) == 1:
            power_right = power_left
        else:
            power_right = np.square(deinterleaved[1], dtype=np.int64)

        sum_left = np.sum(power_left)
        sum_right = np.sum(power_right)

        if sum_left > 0:
            vol_left = 20 * log10(sqrt(sum_left / frame_count))
        else:
            vol_left = 0

        if sum_right > 0:
            vol_right = 20 * log10(sqrt(sum_right / frame_count))
        else:
            vol_right = 0

        # Callbacks

        for callback in self.__level_callbacks:
            callback(vol_left, vol_right)

    def register_levels_callback(self, callback: Callable[[float, float], None]):
        self.__level_callbacks.append(callback)
        self.__logger.info(f"{self.LOG_PREFIX}: register levels callback %s", callback)

    def deregister_levels_callback(self, callback: Callable[[float, float], None]):
        if callback in self.__level_callbacks:
            self.__level_callbacks.remove(callback)
        self.__logger.info(
            f"{self.LOG_PREFIX}: deregister levels callback %s", callback
        )
