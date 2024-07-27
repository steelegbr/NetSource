from enum import StrEnum
from services.audio import AudioService
from services.logging import get_logger, Logger
from typing import Callable, List


class ScheduleServiceStatus(StrEnum):
    Stopped = "STOP"
    Started = "START"
    Error = "ERROR"


class ScheduleService:
    __audio_service: AudioService
    __callbacks: List[Callable[[ScheduleServiceStatus], None]]
    __instance = None
    __logger: Logger
    __status: ScheduleServiceStatus

    LOG_PREFIX = "Schedule Service"

    def __init__(self) -> None:
        raise RuntimeError(
            "Direct instantiation not permitted, call ScheduleService.instance() instead"
        )

    @classmethod
    def instance(cls, logger: Logger = get_logger(__name__)):
        if cls.__instance is None:
            cls.__instance = cls.__new__(cls)
            cls.__instance.__audio_service = AudioService.instance()
            cls.__instance.__callbacks = []
            cls.__instance.__logger = logger
            cls.__status = ScheduleServiceStatus.Stopped
        return cls.__instance

    def __set_status(self, status: ScheduleServiceStatus):
        self.__status = status
        for callback in self.__callbacks:
            callback(self.__status)

    def get_status(self) -> ScheduleServiceStatus:
        return self.__status

    def deregister_callback(self, callback: Callable[[ScheduleServiceStatus], None]):
        if callback in self.__callbacks:
            self.__callbacks.remove(callback)
        self.__logger.info(f"{self.LOG_PREFIX}: deregister callback %s", callback)

    def register_callback(self, callback: Callable[[ScheduleServiceStatus], None]):
        self.__callbacks.append(callback)
        self.__logger.info(f"{self.LOG_PREFIX}: register callback %s", callback)
        callback(self.get_status())

    def start(self):
        self.__set_status(ScheduleServiceStatus.Started)
        self.__logger.info(f"{self.LOG_PREFIX}: Started")

    def stop(self):
        self.__set_status(ScheduleServiceStatus.Stopped)
        self.__logger.info(f"{self.LOG_PREFIX}: Stopped")
