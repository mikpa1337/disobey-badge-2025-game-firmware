import asyncio
import random

from bdg.utils import fwdbutton
from bdg.msg import BadgeAdr, null_badge_adr
from bdg.msg.connection import NowListener
from bdg.asyncbutton import ButtonEvents
from bdg.utils import singleton, Timer
from bdg.config import Config
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from bdg.screens.scan_screen import ScannerScreen
from bdg.screens.solo_games_screen import SoloGamesScreen
from bdg.game_registry import get_registry
from gui.core.colors import GREEN, BLACK, D_PINK, WHITE, D_GREEN, D_RED
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.fonts import arial35, freesans20, font10
from gui.primitives import launch
from gui.widgets.buttons import Button, RECTANGLE
from gui.widgets.label import Label


class BadgeCooldown(Exception):
    def __init__(self, message="Badge in cooldown"):
        super().__init__(message)


@singleton
class BadgeGame:
    def __init__(self):
        self.opponent_timer = Timer(60, cb=self.clear_opponent)
        self.opponent_cooldown_t = Timer(30)
        self.opponent = None
        self._old_opponent = None
        self.opponent_timer.stop()

    def clear_opponent(self):
        self._old_opponent = self.opponent
        self.opponent = None
        self.opponent_cooldown_t.start()

    def has_opponent(self) -> bool:
        return self.opponent is not None

    def acquire_opponent(self) -> BadgeAdr:
        """
        Attempts to acquire an opponent from the list of last seen entities and starts the
        opponent timer if successful. The method checks two conditions before selecting
        an opponent: whether the opponent timer is still active and whether the cooldown
        timer for the badge is active. If either condition is true, it raises a
        BadgeCooldown exception. If no opponents are available in the list, a null
        badge address is returned.

        :raises BadgeCooldown: If the opponent timer is still active with remaining time
            or if the badge cooldown timer is active.
        :return: The address of the selected opponent if successfully acquired, or
            a null badge address if no opponents are available.
        """
        if self.opponent_timer.is_act():
            raise BadgeCooldown("Opponent still active {opponent_timer.time_left()}s ")
        else:
            if self.opponent_cooldown_t.is_act():
                raise BadgeCooldown(
                    "Badge in cooldown {opponent_cooldown_t.time_left()}s "
                )

        if len(NowListener.last_seen):
            self.opponent = random.choice(NowListener.last_seen.keys())
            self.opponent_timer.start()
            return self.opponent

        return null_badge_adr


class GameLobbyScr(Screen):
    sync_update = True  # set screen update mode synchronous

    def __init__(self):
        super().__init__()
        self.game = BadgeGame()
        # verbose default indicates if fast rendering is enabled
        wri = CWriter(ssd, font10, WHITE, BLACK, verbose=False)
        wrib = CWriter(ssd, arial35, D_PINK, BLACK, verbose=False)
        self.nick_lbl = Label(wri, 0, 100, 120, bdcolor=False, justify=1)

        self.lbl_i = Label(
            wri, 170 // 3, 2, 316, bdcolor=False, justify=1, fgcolor=D_GREEN
        )

        self.lbl_s = Label(wrib, 170 // 3 + 20, 2, 316, bdcolor=False, justify=1)
        self.lbl_i.value("Badge is")
        self.lbl_s.value("ACTIVE")

        # Check if there are multiplayer games available
        registry = get_registry()
        multiplayer_games = [g for g in registry.get_all_games() if g.get("multiplayer", False)]
        has_multiplayer = len(multiplayer_games) > 0
        
        # Check if there are solo games available
        solo_games = [g for g in registry.get_all_games() if not g.get("multiplayer", False)]
        has_solo = len(solo_games) > 0
        
        print(f"GameLobbyScr: {len(multiplayer_games)} multiplayer games, {len(solo_games)} solo games")

        # Multi button (left side) - opens ScannerScreen for multiplayer
        def multi_cb(button):
            Screen.change(ScannerScreen)

        self.multi_btn = Button(
            wri,
            170 - 30,
            50,
            callback=multi_cb,
            fgcolor=D_PINK,
            bgcolor=BLACK,
            text="Multi",
            shape=RECTANGLE,
            textcolor=D_PINK,
            width=110,
        )
        
        # Disable Multi button if no multiplayer games available
        if not has_multiplayer:
            self.multi_btn.greyed_out(True)

        # Solo button (right side) - will open SoloGamesScreen
        def solo_cb(button):
            print("Solo button pressed - opening SoloGamesScreen")
            Screen.change(SoloGamesScreen)

        self.solo_btn = Button(
            wri,
            170 - 30,
            170,
            callback=solo_cb,
            fgcolor=D_PINK,
            bgcolor=BLACK,
            text="Solo",
            shape=RECTANGLE,
            textcolor=D_PINK,
            width=110,
        )
        
        # Disable Solo button if no solo games available
        if not has_solo:
            self.solo_btn.greyed_out(True)

    def after_open(self):
        self.update_nickname()

    def update_nickname(self):
        self.nick_lbl.value(Config.config["espnow"]["nick"])


class ActiveGameScr(Screen):
    sync_update = True  # set screen update mode synchronous
    MODE_READY = 0
    MODE_SEARCHING = 1
    MODE_NO_OPPONENT = 2

    def __init__(self):
        super().__init__()
        self.game = None

        self.mode = self.MODE_READY
        # verbose default indicates if fast rendering is enabled
        self.opponent: BadgeAdr = None
        wri = CWriter(ssd, font10, WHITE, BLACK, verbose=False)
        wrib = CWriter(ssd, arial35, D_PINK, BLACK, verbose=False)
        self.nick_lbl = Label(wri, 0, 100, 120, bdcolor=False, justify=1)

        self.lbl_i = Label(
            wri, 170 // 3 - 30, 2, 316, bdcolor=False, justify=1, fgcolor=D_GREEN
        )
        self.lbl_s = Label(wrib, 170 // 3 - 10, 2, 316, bdcolor=False, justify=1)
        self.lbl_i.value("Badge is")
        self.lbl_s.value("ACTIVE")

        self.lbl_t = Label(
            wri, self.lbl_s.mrow, 2, 316, bdcolor=False, justify=1, fgcolor=D_GREEN
        )
        self.lbl_t.value(f"Opponent:")

        self.track_b = Button(
            wri,
            170 - 60,
            105,
            callback=self.track_cb,
            fgcolor=D_PINK,
            bgcolor=BLACK,
            text="Ready to Play",
            textcolor=D_PINK,
        )

        self.lbl_c = Label(
            wri, self.track_b.mrow + 10, 2, 316, bdcolor=False, justify=1, fgcolor=D_RED
        )

    def track_cb(self, button):
        print("track_cb")
        self.mode = self.MODE_SEARCHING
        self.update_ui()

    async def listen_handler(self):
        async for opponent in NowListener.updates(filer_mac=self.opponent.mac):
            print(f"listen_handler: {opponent}")
            self.opponent = opponent
            self.update_ui()

    def after_open(self):
        self.game = BadgeGame()
        # TODO:

        if not self.game.has_opponent():
            print("Acquiring opponent...")
            try:
                self.opponent = self.game.acquire_opponent()
                print("Acquired opponent:", self.opponent)
                if self.opponent is null_badge_adr:
                    self.mode = self.MODE_NO_OPPONENT
                    print("No opponents available")
                else:
                    self.mode = self.MODE_READY
                    print("Opponent ready:", self.opponent)
            except BadgeCooldown as e:
                # FIXME: jump to cooldown screen
                print("Badge in cooldown:", e)
                Screen.change("CooldownScr", args=[str(e)])
        self.update_ui()

    def update_ui(self):
        self.nick_lbl.value(Config.config["espnow"]["nick"])

        if self.mode == self.MODE_SEARCHING:
            self.track_b.visible = False
            self.lbl_s.value("SEARCHING")
            # TODO: implement changing message from rssi and time
            self.lbl_t.value(f"{self.opponent} signal is too weak!")
        elif self.mode == self.MODE_READY:
            self.track_b.visible = True
            self.lbl_t.value(f"Opponent: {self.opponent}")
            self.lbl_s.value("ACTIVE")
        else:  # mode=self.MODE_NO_OPPONENT
            self.track_b.visible = True
            self.lbl_c.visible = False
            if self.opponent == null_badge_adr:
                self.lbl_t.value(f"No opponents available")
                self.lbl_s.value("CONNECTION LOST")
            else:
                # TODO: contextful message of reason
                self.lbl_t.value(f"{self.opponent} got away!")
                self.lbl_s.value("CONNECTION LOST")

        self.lbl_c.value(f"Time Left:{self.time_left()}")

    def time_left(self):
        self.game.opponent_timer.time_left()
        return "5min 30s"


async def start_game():
    print("start_game")
    Screen.change(GameLobbyScr, mode=Screen.REPLACE)
