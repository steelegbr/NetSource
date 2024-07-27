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
from typing import Any, Callable, Dict, List, Tuple
from utils.audio.converters import AudioConverter
from utils.audio.buffers import PlayThroughSampleBuffer, SampleBuffer, ToneSampleBuffer


class AudioEngineState(StrEnum):
    Stopped = "STOP"
    Started = "START"
    Error = "ERROR"
    FadeIn = "FADE_IN"
    FadeOut = "FADE_OUT"
    Relaying = "RELAYING"


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
    __audio_converter: AudioConverter
    __buffer: PlayThroughSampleBuffer
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
    __playlist: List[SampleBuffer] = []

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
            cls.__instance.__audio_converter = AudioConverter()
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

        if self.__state == AudioEngineState.Relaying:
            self.fade_out()

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
            self.__pa.get_format_from_width(self.WORD_SIZE, False),
            True,
            False,
            self.__input_device.id,
            stream_callback=self.__record_callback,
        )
        self.__stream_out = self.__pa.open(
            self.SAMPLE_RATE,
            self.__calculate_channel_count(False),
            self.__pa.get_format_from_width(self.WORD_SIZE, False),
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

    def __record_callback(
        self, in_data: bytes, frame_count: int, time_info: Dict, status
    ):
        deinterleved = self.__audio_converter.bytes_to_deinterleaved(
            in_data, self.__calculate_channel_count(True), self.WORD_SIZE
        )

        stereo_deinterleved = (
            deinterleved
            if len(deinterleved) > 1
            else [deinterleved[0], deinterleved[0]]
        )

        if self.__state in [
            AudioEngineState.FadeIn,
            AudioEngineState.Relaying,
            AudioEngineState.FadeOut,
        ]:
            self.__buffer.write(stereo_deinterleved)

        # self.__logger.info(
        #     f"{self.LOG_PREFIX}: %d decoded vs %d expected and width of %d for %d channels on a buffer of %d bytes",
        #     len(stereo_deinterleved[0]),
        #     frame_count,
        #     self.WORD_SIZE,
        #     self.__calculate_channel_count(True),
        #     len(in_data),
        # )

        vol_left, vol_right = self.__calculate_levels(stereo_deinterleved)
        for callback in self.__level_callbacks_input:
            callback(vol_left, vol_right)

        return (in_data, paContinue)

    def __play_callback(
        self, in_data: bytes, frame_count: int, time_info: Dict, status
    ):
        # Blank buffers for mixing

        data = [
            np.zeros(frame_count, self.__calculate_numpy_type()),
            np.zeros(frame_count, self.__calculate_numpy_type()),
        ]

        # Relaying

        if self.__state in [
            AudioEngineState.FadeIn,
            AudioEngineState.Relaying,
            AudioEngineState.FadeOut,
        ]:
            data = self.__relay(frame_count, data)

        # Playing through a playlist of buffers

        if self.__state in [AudioEngineState.Started]:
            data = self.__play_playlist(frame_count)

        # Levels

        vol_left, vol_right = self.__calculate_levels(data)
        for callback in self.__level_callbacks_output:
            callback(vol_left, vol_right)

        # Pass into the next stage

        output = np.empty(frame_count * 2, self.__calculate_numpy_type())
        output[0::2] = data[0]
        output[1::2] = data[1]

        return (output.tobytes(), paContinue)

    def __play_playlist(
        self, frame_count: int
    ) -> List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]:
        samples_remaining = frame_count
        left = np.array([], self.__calculate_numpy_type())
        right = np.array([], self.__calculate_numpy_type())

        # Work through the playlist until we fill the buffer

        while samples_remaining:

            try:
                current_item = self.__playlist.pop(0)
            except IndexError:
                # We've run out of things to play
                # Pad out the remaining buffer with zeros

                left = np.append(
                    left, np.zeros(samples_remaining, self.__calculate_numpy_type())
                )
                right = np.append(
                    right, np.zeros(samples_remaining, self.__calculate_numpy_type())
                )
                return [left, right]

            # Copy what we can in

            item_data = current_item.read(samples_remaining)
            left = np.append(left, item_data[0][:samples_remaining])
            right = np.append(right, item_data[1][:samples_remaining])

            # Have we finished?
            # If we have, put the current item back
            # If not, crack on through the playlist

            samples_remaining = max(0, frame_count - len(left))
            if not samples_remaining:
                self.__playlist.insert(0, current_item)

        return [left, right]

    def __relay(
        self,
        frame_count: int,
        data: List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]],
    ) -> List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]:
        relay_data = self.__buffer.read(frame_count)
        left = np.add(data[0], relay_data[0][:frame_count])
        right = np.add(data[1], relay_data[1][:frame_count])
        data = [left, right]

        if self.__state == AudioEngineState.FadeIn:
            self.__logger.info(f"{self.LOG_PREFIX}: move from fade in to relaying")
            self.__state = AudioEngineState.Relaying

        if self.__state == AudioEngineState.FadeOut:
            self.__logger.info(f"{self.LOG_PREFIX}: move from fade out to stopped")
            self.__state = AudioEngineState.Started

        return data

    def __calculate_levels(
        self, data: List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]
    ) -> Tuple[int, int]:
        # Calculate a VU number
        # We force stereo

        power_left = np.square(data[0], dtype=np.int64)
        if len(data) == 1:
            power_right = power_left
        else:
            power_right = np.square(data[1], dtype=np.int64)

        sum_left = np.sum(power_left)
        sum_right = np.sum(power_right)

        frame_count = min(len(power_left), len(power_right))

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

    def __calculate_numpy_type(self):
        if self.WORD_SIZE == 2:
            return np.int16
        return np.int8

    def fade_in(self):
        if not self.__state == AudioEngineState.Started:
            self.__logger.warn(
                f"{self.LOG_PREFIX}: fade in not possible as engine is in %s state",
                self.__state,
            )
            return

        self.__buffer = PlayThroughSampleBuffer(self.__calculate_numpy_type())
        self.__state = AudioEngineState.FadeIn

    def fade_out(self):
        if not self.__state == AudioEngineState.Relaying:
            self.__logger.warn(
                f"{self.LOG_PREFIX}: fade out not possible as engine is in %s state",
                self.__state,
            )
            return

        self.__state = AudioEngineState.FadeOut

    def play_tone(self, frequency: int, length: float, level_dbfs: int):
        self.__logger.info(
            f"{self.LOG_PREFIX}: request for tone at %d Hz (%d dbFS) for %d seconds",
            frequency,
            level_dbfs,
            length,
        )
        tone = ToneSampleBuffer(
            self.__calculate_numpy_type(),
            self.SAMPLE_RATE,
            frequency,
            length,
            level_dbfs,
        )
        self.__playlist.append(tone)
