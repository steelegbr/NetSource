from logging import Logger
from pyttsx3 import init as pttsx3_init
from services.logging import get_logger
from services.settings import Settings, SettingsService


class TextToSpeechService:
    __instance = None
    __logger: Logger

    LOG_PREFIX = "TTS Service"

    def __init__(self) -> None:
        raise RuntimeError(
            "Direct instantiation not permitted, call TexttoSpeech.instance() instead"
        )

    @classmethod
    def instance(cls, logger: Logger = get_logger(__name__)):
        if cls.__instance is None:
            cls.__instance = cls.__new__(cls)
            cls.__instance.__logger = logger
        cls.__instance.__generate_holding_message()
        return cls.__instance

    def __generate_holding_message(self):
        settings = SettingsService().get()

        self.__logger.info(
            f"{self.LOG_PREFIX}: generating holding message with content '%s'",
            settings.holding_message,
        )
        engine = pttsx3_init("espeak")
        engine.say(settings.holding_message)
        engine.runAndWait()
