import numpy as np
from services.logging import get_logger, Logger
from typing import Any, List


class AudioConverter:
    def __calculate_numpy_type(self, word_size: int):
        if word_size == 2:
            return np.int16
        return np.int8

    def bytes_to_deinterleaved(
        self, data: bytes, channel_count: int, word_size: int
    ) -> List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]:
        frames = np.frombuffer(data, self.__calculate_numpy_type(word_size))
        return [frames[idx::channel_count] for idx in range(channel_count)]


class PlayThroughSampleBuffer:
    __logger: Logger
    __samples_left: np.ndarray[Any, np.dtype[np.int16 | np.int8]]
    __samples_right: np.ndarray[Any, np.dtype[np.int16 | np.int8]]
    __type: np.int16 | np.int8

    LOG_PREFIX = "Play Through Sample Buffer"

    def __init__(
        self, buffer_type: np.int16 | np.int8, preload_length: int = 500
    ) -> None:
        self.__logger = get_logger(__name__)
        self.__type = buffer_type
        self.__clear_buffer(preload_length)

    def __clear_buffer(self, preload_length: int = 0):
        self.__samples_left = np.array([0] * preload_length, self.__type)
        self.__samples_right = np.array([0] * preload_length, self.__type)

    def read(
        self, sample_count: int
    ) -> List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]:
        buffer_length = min(len(self.__samples_left), len(self.__samples_right))

        if sample_count > buffer_length:
            underrun_length = sample_count - buffer_length
            self.__logger.warn(
                f"{self.LOG_PREFIX}: buffer underrun by %d sample(s)", underrun_length
            )

            left_pad = np.array([0] * underrun_length, self.__type)
            left = np.append(left_pad, self.__samples_left)
            right = np.append(left_pad, self.__samples_right)

            self.__clear_buffer()
            return [left, right]

        left = self.__samples_left[:sample_count]
        right = self.__samples_right[:sample_count]
        self.__samples_left = self.__samples_left[sample_count:]
        self.__samples_right = self.__samples_right[sample_count:]
        return [left, right]

    def write(self, samples: List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]):
        len_left = len(samples[0])
        len_right = len(samples[1])
        length = min(len_left, len_right)

        if not len_left == len_right:
            self.__logger.warn(
                f"{self.LOG_PREFIX}: buffer length mismatch - %d vs %d, so assuming %d",
                len_left,
                len_right,
                length,
            )

        self.__samples_left = np.append(self.__samples_left, samples[0])
        self.__samples_right = np.append(self.__samples_right, samples[1])
