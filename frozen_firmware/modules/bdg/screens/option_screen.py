from bdg.screens.solo_games_screen import SoloGamesScreen
from gui.fonts import freesans20, font10
from gui.core.colors import *
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter

from gui.widgets import Label, Listbox
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from bdg.badge_game import GameLobbyScr
from bdg.screens.ota import OTAScreen
from bdg.config import Config
from bdg.version import Version

class OptionScreen(Screen):
    sync_update = True  # set screen update mode synchronous

    def __init__(self, espnow = None, sta = None):
        super().__init__()
        # verbose default indicates if fast rendering is enabled
        wri = CWriter(ssd, freesans20, GREEN, BLACK, verbose=False)
        wri_pink = CWriter(ssd, font10, D_PINK, BLACK, verbose=False)
        self.els = [
            "Home",
            "Firmware update",
            "Solo games & apps",
        ]

        self.espnow = espnow
        self.sta = sta

        # No longer add individual solo games

                
        self.lbl_w = Label(
            wri,
            10,
            2,
            316,
            bdcolor=False,
            justify=Label.CENTRE,
        )
        self.lbl_w.value("Menu")
        self.lb = Listbox(
            wri_pink,
            50,
            2,
            width=316,
            elements=self.els,
            dlines=6,
            bdcolor=D_PINK,
            callback=self.lbcb,
            also=Listbox.ON_LEAVE,
        )

        HiddenActiveWidget(wri)

    def lbcb(self, lb):  # Listbox callback
        selected = lb.textvalue()

        if selected == "Home":
            Screen.change(GameLobbyScr)
        elif selected == "Firmware update":
            Screen.change(
                OTAScreen,
                mode=Screen.STACK,
                kwargs={
                    "espnow": self.espnow,
                    "sta": self.sta,
                    "fw_version": Version().version,
                    "ota_config": Config.config["ota"],
                },
            )
        elif selected == "Solo games & apps":
            Screen.change(SoloGamesScreen, mode=Screen.STACK)
