import schedule
from calendar import day_name
from datetime import datetime, timedelta
from dateutil.rrule import rrule, WEEKLY
from enum import StrEnum
from models.settings import Settings
from services.audio import AudioService
from services.logging import get_logger, Logger
from services.settings import SettingsService
from threading import Thread
from time import sleep
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
    __run_schedule: bool = False
    __settings_service: SettingsService
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
            cls.__instance.__settings_service = SettingsService()
            cls.__instance.__status = ScheduleServiceStatus.Stopped
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

    def __run(self):
        while self.__run_schedule:
            schedule.run_pending()
            sleep(0.5)

    def start(self):
        self.__set_status(ScheduleServiceStatus.Started)
        self.__logger.info(f"{self.LOG_PREFIX}: Started")

        # Start the background thread

        self.__run_schedule = True
        Thread(target=self.__run).start()

        # Work out if we're between the start and finish times
        # Start by going back to the last opening time
        # Then work out the end time that follows

        settings: Settings = self.__settings_service.get()
        last_start = rrule(
            WEEKLY,
            datetime.now() - timedelta(weeks=1),
            byweekday=settings.day_start,
            byhour=settings.time_start.hour,
            byminute=settings.time_start.minute,
            bysecond=settings.time_start.second,
        ).before(datetime.now(), True)
        self.__logger.info(
            f"{self.LOG_PREFIX}: Determined last event start to be %s", last_start
        )

        following_finish = rrule(
            WEEKLY,
            datetime.now() - timedelta(weeks=1),
            byweekday=settings.day_end,
            byhour=settings.time_end.hour,
            byminute=settings.time_end.minute,
            bysecond=settings.time_end.second,
        ).after(last_start, True)
        self.__logger.info(
            f"{self.LOG_PREFIX}: Determined following finish to be %s", following_finish
        )

        if datetime.now() < following_finish:
            self.start_show()
        else:
            self.end_show()

    def start_show(self):
        self.__logger.info(f"{self.LOG_PREFIX}: Start show called")
        self.__audio_service.fade_in()
        schedule.clear()

        # Schedule the end of the show

        settings = self.__settings_service.get()

        match settings.day_end:
            case 0:
                schedule.every().monday.at(str(settings.time_end)).do(self.end_show)
            case 1:
                schedule.every().tuesday.at(str(settings.time_end)).do(self.end_show)
            case 2:
                schedule.every().wednesday.at(str(settings.time_end)).do(self.end_show)
            case 3:
                schedule.every().thursday.at(str(settings.time_end)).do(self.end_show)
            case 4:
                schedule.every().friday.at(str(settings.time_end)).do(self.end_show)
            case 5:
                schedule.every().saturday.at(str(settings.time_end)).do(self.end_show)
            case 6:
                schedule.every().sunday.at(str(settings.time_end)).do(self.end_show)

    def end_show(self):
        self.__logger.info(f"{self.LOG_PREFIX}: End show called")
        self.__audio_service.fade_out()
        schedule.clear()

        # Next show

        settings: Settings = self.__settings_service.get()

        match settings.day_start:
            case 0:
                schedule.every().monday.at(str(settings.time_start)).do(self.start_show)
            case 1:
                schedule.every().tuesday.at(str(settings.time_start)).do(
                    self.start_show
                )
            case 2:
                schedule.every().wednesday.at(str(settings.time_start)).do(
                    self.start_show
                )
            case 3:
                schedule.every().thursday.at(str(settings.time_start)).do(
                    self.start_show
                )
            case 4:
                schedule.every().friday.at(str(settings.time_start)).do(self.start_show)
            case 5:
                schedule.every().saturday.at(str(settings.time_start)).do(
                    self.start_show
                )
            case 6:
                schedule.every().sunday.at(str(settings.time_start)).do(self.start_show)

        # Calculate a bleep schedule

        next_start = rrule(
            WEEKLY,
            datetime.now(),
            byweekday=settings.day_start,
            byhour=settings.time_start.hour,
            byminute=settings.time_start.minute,
            bysecond=settings.time_start.second,
        ).after(datetime.now(), True)
        self.__logger.info(
            f"{self.LOG_PREFIX}: Determined next show start to be %s", next_start
        )

        beeps_end = next_start + timedelta(seconds=-10)
        self.__logger.info(f"{self.LOG_PREFIX}: Bleeps will end at %s", beeps_end)

        schedule.every().minute.at(":00").until(beeps_end).do(self.__beep_long)
        schedule.every().minute.at(":10").until(beeps_end).do(self.__beep_short)
        schedule.every().minute.at(":20").until(beeps_end).do(self.__beep_short)
        schedule.every().minute.at(":30").until(beeps_end).do(self.__beep_short)
        schedule.every().minute.at(":40").until(beeps_end).do(self.__beep_short)
        schedule.every().minute.at(":50").until(beeps_end).do(self.__beep_short)

    def __beep_long(self):
        settings: Settings = self.__settings_service.get()
        self.__audio_service.play_tone(
            settings.beep_frequency,
            settings.beep_long,
            settings.beep_dbfs,
        )

    def __beep_short(self):
        settings: Settings = self.__settings_service.get()
        self.__audio_service.play_tone(
            settings.beep_frequency, settings.beep_short, settings.beep_dbfs
        )

    def stop(self):
        self.__set_status(ScheduleServiceStatus.Stopped)
        self.__logger.info(f"{self.LOG_PREFIX}: Stopped")
        self.__run_schedule = False

        # Clear the schedule

        schedule.clear()

        # Stop any audio processes

        self.__audio_service.fade_out()

    def days_of_week(self):
        return day_name
