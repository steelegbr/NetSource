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
from typing import Callable, Dict, List, Tuple


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
    __level_callbacks_input: List[Callable[[float, float], None]]
    __level_callbacks_output: List[Callable[[float, float], None]]
    __logger: Logger
    __output_device: SoundCard
    __pa: PyAudio
    __state: AudioEngineState
    __stream_in: Stream
    __stream_out: Stream

    LOG_PREFIX = "Audio Service"
    SAMPLE_RATE = 48000
    STEREO = 2
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
            cls.__instance.__level_callbacks_input = []
            cls.__instance.__level_callbacks_output = []
            cls.__instance.__logger = logger
            cls.__instance.__output_device = None
            cls.__pa = PyAudio()
            cls.__state = AudioEngineState.Stopped
        return cls.__instance

    def get_soundcards(self, input: bool) -> List[SoundCard]:
        device_count = self.__pa.get_device_count()
        self.__logger.info(f"{self.LOG_PREFIX}: found %d device(s)", device_count)

        sound_cards: List[SoundCard] = []

        for i in range(0, device_count):
            current_device = self.__pa.get_device_info_by_index(i)
            if input and current_device["maxInputChannels"] > 0:
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
            elif not input and current_device["maxOutputChannels"] >= self.STEREO:
                sound_card = SoundCard(
                    channels=current_device["maxOutputChannels"],
                    engine=current_device["hostApi"],
                    id=current_device["index"],
                    name=current_device["name"],
                )
                self.__logger.info(
                    f"{self.LOG_PREFIX}: mapped sound card %s", sound_card
                )
                sound_cards.append(sound_card)

        self.__logger.info(
            f"{self.LOG_PREFIX}: found %d %s device(s)",
            len(sound_cards),
            "recording" if input else "playback",
        )
        return sound_cards

    def set_input_device(self, sound_card: SoundCard):
        self.__logger.info(f"{self.LOG_PREFIX}: set input device to %s", sound_card)
        if not self.__input_device == sound_card:
            if self.__state == AudioEngineState.Started:
                self.stop()
            self.__input_device = sound_card
            self.start()

    def set_output_device(self, sound_card: SoundCard):
        self.__logger.info(f"{self.LOG_PREFIX}: set output device to %s", sound_card)
        if not self.__output_device == sound_card:
            if self.__state == AudioEngineState.Started:
                self.stop()
            self.__output_device = sound_card
            self.start()

    def stop(self):
        self.__logger.info(f"{self.LOG_PREFIX}: stop audio engine")
        if self.__stream_in:
            self.__stream_in.stop_stream()
            self.__stream_in.close()
            self.__stream_in = None
        if self.__stream_out:
            self.__stream_out.stop_stream()
            self.__stream_out.close()
            self.__stream_out = None

    def start(self):
        if not (self.__input_device and self.__output_device):
            self.__logger.warn(
                f"{self.LOG_PREFIX}: failed to start audio engine as we need both devices"
            )
            return

        self.__logger.info(
            f"{self.LOG_PREFIX}: start audio engine on devices %s", self.__input_device
        )
        self.__stream_in = self.__pa.open(
            self.SAMPLE_RATE,
            self.__calculate_channel_count(True),
            self.__pa.get_format_from_width(self.WORD_SIZE),
            True,
            False,
            self.__input_device.id,
            stream_callback=self.__record_callback,
        )
        self.__stream_out = self.__pa.open(
            self.SAMPLE_RATE,
            self.__calculate_channel_count(False),
            self.__pa.get_format_from_width(self.WORD_SIZE),
            False,
            True,
            self.__output_device.id,
            stream_callback=self.__play_callback,
        )
        self.__state = AudioEngineState.Started

    def __calculate_channel_count(self, input: bool) -> int:
        if input:
            return min(self.__input_device.channels, self.STEREO)
        return self.STEREO

    def __calculate_numpy_type(self):
        if self.WORD_SIZE == 2:
            return np.int16
        return np.int8

    def __record_callback(
        self, in_data: bytes, frame_count: int, time_info: Dict, status
    ):
        vol_left, vol_right = self.__calculate_levels(
            in_data, self.__calculate_channel_count(True), frame_count
        )
        for callback in self.__level_callbacks_input:
            callback(vol_left, vol_right)

        return (in_data, paContinue)

    def __play_callback(
        self, in_data: bytes, frame_count: int, time_info: Dict, status
    ):
        data = b"\x00" * frame_count
        vol_left, vol_right = self.__calculate_levels(
            data, self.__calculate_channel_count(False), frame_count
        )
        for callback in self.__level_callbacks_output:
            callback(vol_left, vol_right)

        return (data, paContinue)

    def __calculate_levels(
        self, data: bytes, channel_count: int, frame_count: int
    ) -> Tuple[int, int]:
        # Decode and deinterleve

        frames = np.frombuffer(data, self.__calculate_numpy_type())
        deinterleaved = [frames[idx::channel_count] for idx in range(channel_count)]

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

        return (vol_left, vol_right)

    def register_levels_callback(
        self, input: bool, callback: Callable[[float, float], None]
    ):
        if input:
            self.__level_callbacks_input.append(callback)
        else:
            self.__level_callbacks_output.append(callback)
        self.__logger.info(
            f"{self.LOG_PREFIX}: register %s levels callback %s",
            "input" if input else "output",
            callback,
        )

    def deregister_levels_callback(
        self, input: bool, callback: Callable[[float, float], None]
    ):
        if input and callback in self.__level_callbacks_input:
            self.__level_callbacks_input.remove(callback)
        elif not input and callback in self.__level_callbacks_output:
            self.__level_callbacks_output.remove(callback)
        self.__logger.info(
            f"{self.LOG_PREFIX}: deregister %s levels callback %s",
            "input" if input else "output",
            callback,
        )
