from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.properties import ListProperty, StringProperty
from services.audio import AudioService, SoundCard
from services.settings import SettingsService
from services.schedule import ScheduleService, ScheduleServiceStatus
from typing import Dict, List


class ScheduleServiceBanner(BoxLayout):
    button_text = StringProperty("")
    status_colour = ListProperty([1, 1, 1, 1])
    status_text = StringProperty("")

    __schedule_service: ScheduleService

    AUDIO_SERVICE_BUTTON_TEXT_MAP: Dict[ScheduleServiceStatus, str] = {
        ScheduleServiceStatus.Error: "Start NetSource",
        ScheduleServiceStatus.Started: "Stop NetSource",
        ScheduleServiceStatus.Stopped: "Start NetSource",
    }

    AUDIO_SERVICE_BACKGROUND_COLOUR_MAP: Dict[ScheduleService, List[float]] = {
        ScheduleServiceStatus.Error: [0.94, 0.55, 0.2, 1],
        ScheduleServiceStatus.Started: [0.13, 0.55, 0.1, 1],
        ScheduleServiceStatus.Stopped: [1, 0, 0, 1],
    }

    AUDIO_SERVICE_DESCRIPTION_MAP: Dict[ScheduleServiceStatus, str] = {
        ScheduleServiceStatus.Error: "Error",
        ScheduleServiceStatus.Started: "Started",
        ScheduleServiceStatus.Stopped: "Stopped",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__schedule_service = ScheduleService.instance()
        self.__schedule_service.register_callback(self.__schedule_service_callback)

    def __schedule_service_callback(self, status: ScheduleServiceStatus):
        self.button_text = self.AUDIO_SERVICE_BUTTON_TEXT_MAP[status]
        self.status_colour = self.AUDIO_SERVICE_BACKGROUND_COLOUR_MAP[status]
        self.status_text = self.AUDIO_SERVICE_DESCRIPTION_MAP[status]

    def toggle_schedule_service(self):
        match self.__schedule_service.get_status():
            case ScheduleServiceStatus.Stopped:
                self.__schedule_service.start()
            case _:
                self.__schedule_service.stop()


class AudioInputBlock(BoxLayout):
    selected_sound_card = StringProperty("")
    sound_cards = ListProperty([])

    __audio_service: AudioService
    __settings_service: SettingsService
    __sound_cards: List[SoundCard]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Enumerate sound cards

        self.__audio_service = AudioService.instance()
        self.__sound_cards = self.__audio_service.get_soundcards()
        self.sound_cards = [
            self.__serialise(sound_card) for sound_card in self.__sound_cards
        ]

        # Set the option from last time (if we have it)

        self.__settings_service = SettingsService()
        settings = self.__settings_service.get()
        self.selected_sound_card = settings.input_device
        self.change_sound_card(settings.input_device)

    def __serialise(self, sound_card: SoundCard) -> str:
        return f"[{sound_card.id}][{sound_card.engine}] {sound_card.name}"

    def change_sound_card(self, sound_card_text: str):
        possible_sound_cards = [
            sound_card
            for sound_card in self.__sound_cards
            if self.__serialise(sound_card) == sound_card_text
        ]

        if possible_sound_cards:
            settings = self.__settings_service.get()
            settings.input_device = sound_card_text
            self.__settings_service.save(settings)
            self.__audio_service.set_input_device(possible_sound_cards[0])


class HomeScreen(GridLayout):
    pass
