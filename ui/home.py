from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.properties import ListProperty, StringProperty
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


class HomeScreen(GridLayout):
    pass
