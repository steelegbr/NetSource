import numpy as np
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
