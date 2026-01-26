import asyncio

from bdg.game_registry import init_game_registry, get_registry
from bdg.screens.solo_games_screen import SoloGamesScreen
from gui.fonts import freesans20, font10
from gui.core.colors import *
from gui.core.ugui import Screen, ssd, quiet
from gui.core.writer import CWriter
from bdg.utils import blit

from gui.widgets import Label, Button, Listbox
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
            value=1,
            bdcolor=D_PINK,
            callback=self.lbcb,
            also=Listbox.ON_LEAVE,
        )

        HiddenActiveWidget(wri) 

    def on_open(self):
        # register callback that will make new connection dialog to pop up
        pass

    def on_hide(self):
        # executed when any other window is opened on top
        pass

    def after_open(self):
        self.show(True) 

    async def update_sprite(self):
        # example of using sprite
        print(">>>> new update_sprite task")
        x = self.sprite.col
        y = self.sprite.row
        t = 0.0
        await asyncio.sleep(1)
        self.sprite.visible = True
        try:
            while True:
                self.sprite.update(
                    y + int(cos(t) * 10.0),
                    x + int(sin(t) * 20.0),
                    True,
                )
                await asyncio.sleep_ms(50)
                t += 0.3
        except asyncio.CancelledError:
            self.sprite.visible = False

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
