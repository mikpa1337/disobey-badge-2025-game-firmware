import asyncio
from machine import Pin
from neopixel import NeoPixel

from gui.core.ugui import Screen, ssd, color_map, FOCUS
from bdg.config import Config
from gui.core.writer import CWriter
from gui.widgets import Label, RadioButtons
from gui.fonts import font10, font14
import gui.fonts.arial10 as arial10
from gui.core.colors import *
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from bdg.bleds import clear_leds, dimm_gamma, L_PINK


class Flashy(Screen):
    def __init__(self, sm, *args, **kwargs):
        super().__init__()

        # Optional: customize the focus border color
        color_map[FOCUS] = GREEN

        # Writer for big text (nick)
        self.wri_nick = CWriter(ssd, font14, GREEN, BLACK, verbose=False)

        # Writer for buttons (smaller font)
        self.wri_btn = CWriter(ssd, arial10, GREEN, BLACK, verbose=False)

        # Read nick from config
        nick = Config.config.get("espnow", {}).get("nick", "ANONYMOUS")

        # Display nick
        self.lbl_w = Label(
            self.wri_nick,
            170 // 3 + 5,
            2,
            316,
            bdcolor=False,
            justify=Label.CENTRE,
        )
        self.lbl_w.value(nick)

        # Enable focus handling on buttons
        HiddenActiveWidget(self.wri_btn)

        # --- LED hardware ---
        self.led_power = Pin(17, Pin.OUT)
        self.led_power.value(1)
        self.np = NeoPixel(Pin(18), 10)

        # --- Mode state ---
        self.mode = "blue"  # default mode
        self.running = True

        # --- Radio buttons ---
        table = [
            {"text": "Blue Team", "args": ["blue"]},
            {"text": "Red Team", "args": ["red"]},
            {"text": "Script Kiddie", "args": ["kiddie"]},
        ]

        rb = RadioButtons(DARKGREEN, self.set_mode)
        col = 30
        first_button = True  # flag for the default button
        for t in table:
            btn = rb.add_button(
                self.wri_btn,
                100,
                col,
                width=90,
                height=30,
                textcolor=WHITE,
                fgcolor=GREEN,
                **t,
            )

            # Make the first button active as default
            if first_button:
                btn.active = True  # highlight the button
                self.mode = t["args"][0]  # set self.mode to match
                first_button = False

            col += 100

    # Radio button callback
    def set_mode(self, button, mode):
        print("Mode selected:", mode)
        self.mode = mode

    # Screen lifecycle
    def after_open(self):
        self.reg_task(self.flash_leds(), True)

    def on_hide(self):
        self.running = False
        clear_leds(self.np)
        self.led_power.value(0)

    # LED logic
    async def flash_leds(self):
        calm_colors = dimm_gamma(
            [(0, 0, 255), (30, 100, 255), (20, 20, 255)],
            0.4,
        )

        hacker_colors = dimm_gamma(
            [(255, 0, 0), (180, 0, 50), (255, 0, 100), (255, 0, 255)],
            0.3,
        )

        crazy_colors = dimm_gamma(
            [(255, 0, 0), (0, 255, 0), (0, 0, 255), L_PINK],
            0.6,
        )

        idx = 0

        while self.running:
            if self.mode == "blue":
                colors = calm_colors
                delay = 0.6
                for i in range(len(self.np)):
                    self.np[i] = colors[(idx + i) % len(colors)]

            elif self.mode == "red":
                colors = hacker_colors
                delay = 0.2
                for i in range(len(self.np)):
                    self.np[i] = colors[(idx + i) % len(colors)]

            else:  # script kiddie 😈
                colors = crazy_colors
                delay = 0.08
                for i in range(len(self.np)):
                    self.np[i] = colors[(idx + i * 3) % len(colors)]

            self.np.write()
            idx += 1
            await asyncio.sleep(delay)


def badge_game_config():
    """
    Configuration for Flashy app

    Returns:
        dict: Game configuration with con_id, title, screen_class, etc.
    """
    return {
        "con_id": 5,
        "title": "Flashy",
        "screen_class": Flashy,
        "screen_args": (),  # Connection passed separately by framework
        "multiplayer": False,
        "description": "Name tag with flashy LEDs",
    }
