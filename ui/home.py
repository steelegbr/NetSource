from datetime import time
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from models.settings import Settings
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

    def __init__(
        self,
        audio_service: AudioService = AudioService.instance(),
        settings_service=SettingsService(),
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.__audio_service = audio_service
        self.__settings_service = settings_service
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

        settings: Settings = self.__settings_service.get()

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


class ScheduleSelectBlock(BoxLayout):
    days_of_week = ListProperty([])
    hours = ListProperty([])
    label_text = StringProperty("")
    minutes = ListProperty([])
    selected_day_of_week = StringProperty("")
    selected_hour = StringProperty("")
    selected_minute = StringProperty("")
    selected_second = StringProperty("")
    seconds = ListProperty([])
    start_time = BooleanProperty()

    __schedule_service: ScheduleService
    __settings_service: SettingsService

    def __init__(
        self,
        schedule_service: ScheduleService = ScheduleService.instance(),
        settings_service=SettingsService(),
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.__schedule_service = schedule_service
        self.__settings_service = settings_service
        self.update_values()

    def on_start_time(self, instance, value):
        self.start_time = value
        self.update_values()

    def update_values(self):
        # Set the label text

        if self.start_time:
            self.label_text = "Start At"
        else:
            self.label_text = "End At"

        # Populate days, hours, mins,seconds options

        self.days_of_week = self.__schedule_service.days_of_week()
        self.hours = [f"{i:02}" for i in range(25)]
        self.minutes = [f"{i:02}" for i in range(61)]
        self.seconds = [f"{i:02}" for i in range(61)]

        # Load saved values

        settings: Settings = self.__settings_service.get()

        if self.start_time:
            self.selected_day_of_week = self.__schedule_service.days_of_week()[
                settings.day_start
            ]
        else:
            self.selected_day_of_week = self.__schedule_service.days_of_week()[
                settings.day_end
            ]

        current_time = self.__get_current_time()
        self.selected_hour = f"{current_time.hour:02}"
        self.selected_minute = f"{current_time.minute:02}"
        self.selected_second = f"{current_time.second:02}"

    def change_day_of_week(self, selected_day_of_week: str):
        settings: Settings = self.__settings_service.get()
        if self.start_time:
            settings.day_start = self.days_of_week.index(selected_day_of_week)
        else:
            settings.day_end = self.days_of_week.index(selected_day_of_week)
        self.__settings_service.save(settings)

    def __get_current_time(self) -> time:
        if self.start_time:
            return self.__settings_service.get().time_start
        return self.__settings_service.get().time_end

    def __save_current_time(self, current_time: time):
        settings = self.__settings_service.get()
        if self.start_time:
            settings.time_start = current_time
        else:
            settings.time_end = current_time
        self.__settings_service.save(settings)

    def change_hour(self, selected_hour: str):
        current_time = self.__get_current_time()
        selected_time = time(
            int(selected_hour), current_time.minute, current_time.second
        )
        self.__save_current_time(selected_time)

    def change_minute(self, selected_minute: str):
        current_time = self.__get_current_time()
        selected_time = time(
            current_time.hour, int(selected_minute), current_time.second
        )
        self.__save_current_time(selected_time)

    def change_second(self, selected_second: str):
        current_time = self.__get_current_time()
        selected_time = time(
            current_time.hour, current_time.minute, int(selected_second)
        )
        self.__save_current_time(selected_time)


class HomeScreen(GridLayout):
    pass
