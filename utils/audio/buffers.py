import numpy as np
from abc import ABC, abstractmethod
from services.logging import get_logger, Logger
from typing import Any, List


class SampleBuffer(ABC):
    @abstractmethod
    def read(
        self, sample_count: int
    ) -> List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]:
        pass

    @abstractmethod
    def write(self, samples: List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]):
        pass


class PlayThroughSampleBuffer(SampleBuffer):
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


class ToneSampleBuffer(SampleBuffer):
    __logger: Logger
    __samples_left: np.ndarray[Any, np.dtype[np.int16 | np.int8]]
    __samples_right: np.ndarray[Any, np.dtype[np.int16 | np.int8]]
    __type: np.int16 | np.int8

    LOG_PREFIX = "Tone Sample Buffer"

    def __init__(
        self,
        buffer_type: np.int16 | np.int8,
        sample_rate: int,
        frequency: int,
        length: float,
        level_dbfs: float,
    ):
        self.__logger = get_logger(__name__)
        self.__type = buffer_type
        self.__generate_samples(sample_rate, frequency, length, level_dbfs)

    def __generate_samples(
        self, sample_rate: int, frequency: int, length: float, level_dbfs: float
    ):
        sample_count = int(sample_rate * length)
        self.__logger.info(
            f"{self.LOG_PREFIX}: generating tone buffer at %dHz (%d dBFS) for %d samples",
            frequency,
            level_dbfs,
            sample_count,
        )

        amplitude = np.iinfo(self.__type).max * 10 ** (level_dbfs / 20)

        self.__samples_left = np.sin(
            2 * np.pi * np.arange(sample_count) * frequency / sample_rate
        )
        self.__samples_left = (self.__samples_left * amplitude).astype(self.__type)
        self.__samples_right = np.copy(self.__samples_left)

    def read(
        self, sample_count: int
    ) -> List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]:
        buffer_length = min(len(self.__samples_left), len(self.__samples_right))

        if sample_count > buffer_length:
            return [self.__samples_left, self.__samples_right]

        left = self.__samples_left[:sample_count]
        right = self.__samples_right[:sample_count]
        self.__samples_left = self.__samples_left[sample_count:]
        self.__samples_right = self.__samples_right[sample_count:]
        return [left, right]

    def write(self, samples: List[np.ndarray[Any, np.dtype[np.int16 | np.int8]]]):
        self.__logger.warn(f"{self.LOG_PREFIX}: request to write to tone buffer")
