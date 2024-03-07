from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
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

    def __init__(
        self, schedule_service: ScheduleService = ScheduleService.instance(), **kwargs
    ):
        super().__init__(**kwargs)
        self.__schedule_service = schedule_service
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


class AudioSelectBlock(BoxLayout):
    audio_input = BooleanProperty()
    label_text = StringProperty("")
    selected_sound_card = StringProperty("")
    sound_cards = ListProperty([])

    __audio_service: AudioService
    __settings_service: SettingsService
    __sound_cards: List[SoundCard]

    def __init__(self, audio_service: AudioService = AudioService.instance(), **kwargs):
        super().__init__(**kwargs)
        self.__audio_service = audio_service
        self.update_options()

    def on_audio_input(self, instance, value):
        self.audio_input = value
        self.update_options()

    def update_options(self):
        # Set the label text

        if self.audio_input:
            self.label_text = "Audio Input"
        else:
            self.label_text = "Audio Output"

        # Enumerate sound cards

        self.__sound_cards = self.__audio_service.get_soundcards(self.audio_input)
        self.sound_cards = [
            self.__serialise(sound_card) for sound_card in self.__sound_cards
        ]

        # Set the option from last time (if we have it)

        self.__settings_service = SettingsService()
        settings = self.__settings_service.get()

        if self.audio_input and settings.input_device:
            self.selected_sound_card = settings.input_device
            self.change_sound_card(settings.input_device)
        elif not self.audio_input and settings.output_device:
            self.selected_sound_card = settings.output_device
            self.change_sound_card(settings.output_device)

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

            if self.audio_input:
                settings.input_device = sound_card_text
                self.__settings_service.save(settings)
                self.__audio_service.set_input_device(possible_sound_cards[0])
            else:
                settings.output_device = sound_card_text
                self.__settings_service.save(settings)
                self.__audio_service.set_output_device(possible_sound_cards[0])


class AudioLevelsBlock(GridLayout):
    audio_input = BooleanProperty()
    colour_left = ListProperty([1, 1, 1, 1])
    colour_right = ListProperty([1, 1, 1, 1])
    level_left = NumericProperty(0)
    level_right = NumericProperty(0)

    # Trigger at -3dBFS and -6dBFS

    LEVEL_RED = 10 ** (-3 / 20) * 100
    LEVEL_ORANGE = 10 ** (-6 / 20) * 100
    COLOUR_ORANGE = [0.94, 0.55, 0.2, 1]
    COLOUR_GREEN = [0.13, 0.55, 0.1, 1]
    COLOUR_RED = [1, 0, 0, 1]

    __audio_service: AudioService

    def __init__(self, audio_service: AudioService = AudioService.instance(), **kwargs):
        super().__init__(**kwargs)
        self.__audio_service = audio_service
        self.__register_callback()

    def on_audio_input(self, instance, value):
        self.audio_input = value
        self.__register_callback()

    def __calculate_colour(self, value: float) -> List:
        if value > self.LEVEL_RED:
            return self.COLOUR_RED
        if value > self.LEVEL_ORANGE:
            return self.COLOUR_ORANGE
        return self.COLOUR_GREEN

    def __levels_callback(self, left: float, right: float):
        self.level_left = left
        self.level_right = right
        self.colour_left = self.__calculate_colour(left)
        self.colour_right = self.__calculate_colour(right)

    def __register_callback(self):
        self.__audio_service.deregister_levels_callback(
            not self.audio_input, self.__levels_callback
        )
        self.__audio_service.register_levels_callback(
            self.audio_input, self.__levels_callback
        )


class HomeScreen(GridLayout):
    pass
