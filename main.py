from kivy.app import App
from kivy.uix.widget import Widget


class MainGui(Widget):
    pass


class DarcsApp(App):
    def build(self):
        return MainGui()


if __name__ == '__main__':
    DarcsApp().run()
