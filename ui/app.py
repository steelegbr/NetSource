from kivymd.app import App
from ui.home import HomeScreen


class NetSourceApp(App):
    def build(self):
        return HomeScreen()
