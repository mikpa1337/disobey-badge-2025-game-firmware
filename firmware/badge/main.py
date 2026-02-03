import asyncio
from math import sin, cos

import aioespnow
import network

import gui.fonts.freesans20 as font
import gui.fonts.font10 as font10  # noqa Create a display instance
import hardware_setup
from bdg.screens.boot_screen import BootScr

# import frozen_fs mounts `frozen_fs` as `/readonly_fs`
import frozen_fs
from bdg.config import Config
from bdg.game_registry import init_game_registry
from gui.core.colors import *
from gui.core.ugui import Screen, quiet

from hardware_setup import BtnConfig, LED_PIN, LED_AMOUNT, LED_ACTIVATE_PIN
from .games.reaction_game import ReactionGameScr
from .games.rps import RpsScreen
from bdg.badge_game import start_game

# from .sprite import Sprite
# import sprite
from .bleds import ScoreLeds
from bdg.asyncbutton import ButtonEvents


ScoreLeds(
    LED_PIN,
    LED_AMOUNT,
    LED_ACTIVATE_PIN,
)


def start_badge():
    print("->Badge<-")

    # init button even machine
    ButtonEvents.init(BtnConfig)

    Config.load()

    # Initialize game registry - scan for available games
    init_game_registry()

    channel = int(Config.config["espnow"]["ch"])

    sta = network.WLAN(network.STA_IF)
    # set configured wifi channels
    sta.active(True)
    sta.config(channel=channel)
    sta.config(txpower=10)
    e = aioespnow.AIOESPNow()
    e.active(True)

    # TODO: WE need to define channel
    own_mac = sta.config("mac")
    print(f"MAC: \nmac={own_mac} ")

    quiet()

    # Startup boot screen...
    Screen.change(BootScr, kwargs={"ready_cb": start_game, "espnow": e, "sta": sta})

    # Screen.change(RpsScreen, args=(None,))


start_badge()
