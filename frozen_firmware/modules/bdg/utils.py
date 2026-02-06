import asyncio

from time import time

from gui.primitives import launch


def enum(**enums: int):
    # https://github.com/micropython/micropython-lib/issues/269#issuecomment-1046314507
    return type("Enum", (), enums)


def copy_img_to_mvb(img_file, ssd):
    with open(img_file, "rb") as f:
        rows = int.from_bytes(f.read(2), "big")
        cols = int.from_bytes(f.read(2), "big")
        f.readinto(ssd.mvb)


from framebuf import RGB565, GS4_HMSB, GS8

size = {RGB565: 2, GS4_HMSB: 0, GS8: 1}


def blit(ssd, img, row=0, col=0):
    def scale(x, sz):
        return x * sz if sz else x // 2

    mvb = ssd.mvb  # Memoryview of display's bytearray.
    irows = min(img.rows, ssd.height - row)  # Clip rows
    icols = min(img.cols, ssd.width - col)  # Clip cols
    if (mode := img.mode) != ssd.mode:
        raise ValueError("Image and display have differing modes.")
    sz = size[mode]  # Allow for no. of bytes per pixel
    ibytes = scale(img.cols, sz)  # Bytes per row of unclipped image data
    dbytes = scale(icols, sz)  # Bytes per row to output to display
    dwidth = scale(ssd.width, sz)  # Display width in bytes
    d = scale(row * ssd.width + col, sz)  # Destination index
    s = 0  # Source index
    while irows:
        mvb[d : d + dbytes] = img.data[s : s + dbytes]
        s += ibytes
        d += dwidth
        irows -= 1


def blit_to_buf(ssd, t_mvb, img_height, img_width, pos_y=0, pos_x=0):
    def scale(x, sz):
        return x * sz if sz else x // 2

    mvb = ssd.mvb  # Memoryview of display's bytearray.
    irows = min(img_height, ssd.height - pos_y)  # Clip rows
    icols = min(img_width, ssd.width - pos_x)  # Clip cols
    sz = 2  # Allow for no. of bytes per pixel
    ibytes = scale(img_width, sz)  # Bytes per row of unclipped image data
    dbytes = scale(icols, sz)  # Bytes per row to output to display
    dwidth = scale(ssd.width, sz)  # Display width in bytes
    d = scale(pos_y * ssd.width + pos_x, sz)  # Destination index
    s = 0  # Source index
    while irows:
        #        mvb[d : d + dbytes] = img.data[s : s + dbytes]
        t_mvb[s : s + dbytes] = mvb[d : d + dbytes]

        s += ibytes
        d += dwidth
        irows -= 1


class AProc:
    # A mixed class that ensures that the task() coro is running only once
    # >>> Aproc.start(task=True) returns a task, a new one or the running one
    # >>> Aproc.stop()  # will cancel the running task
    stop_event = asyncio.Event()
    _task = None

    def __init__(self):
        pass

    async def task(self, *args, **kwargs):
        # This needs to be overridden
        print("ERROR: AProc task started!!!!!")
        pass

    async def wait_stop(self):
        await self.stop_event.wait()

    @classmethod
    def start(cls, *args, **kwargs):
        print(f"Starting async {type(cls).__name__}")
        task = kwargs.pop("task", None)
        if task:
            if cls._task and cls._task.done() or not cls._task:
                # now start the task with all args except "task"
                cls._task = asyncio.create_task(cls.task(*args, **kwargs))
                print(f"new task: {cls._task=}")
            return cls._task
        else:
            # sync run, this is missing the logic to ensure single task
            loop = asyncio.get_event_loop()
            loop.run_until_complete(cls.task(*args, **kwargs))

    @classmethod
    def is_running(cls):
        if cls._task and not cls._task.done():
            return True
        return False

    @classmethod
    def stop(cls):
        print(f"Stopping async {cls.__name__}")
        if cls.stop_event:
            cls.stop_event.set()
            cls._task.cancel()
            cls._task = None


def singleton(cls):
    instance = None

    def getinstance(*args, **kwargs):
        nonlocal instance
        if instance is None:
            instance = cls(*args, **kwargs)
        return instance

    return getinstance


class Timer:
    """
    A timer class for managing timeouts and executing callback functions.

    This class allows managing a timeout period with an optional callback
    function to execute when the timeout elapses. It provides methods
    to start, stop, and check the timer's status, as well as measure
    elapsed or remaining time.

    Attributes:
        _timeout_t (asyncio.Task or None): The active asyncio task tracking the timer.
        args (tuple): Arguments passed to the callback function.
        start_time (float or None): Timestamp of when the timer was started.
        end_time (float or None): Timestamp of when the timer was stopped.
        cb (callable or None): Callback function to execute after the timeout.
        timout_s (float): The configured timeout duration, in seconds.
    """

    def __init__(self, timout_s, cb=None, args=(), start=True):
        self._timeout_t = None
        self.args = args
        self.start_time = None
        self.end_time = None
        self.cb = cb
        assert timout_s > 0, "Timeout must be a positive number of seconds."
        self.timout_s = timout_s
        if start:
            self.start()

    def start(self):
        if not self.is_act():
            self.start_time = time()
            self.end_time = None
            self._timeout_t = asyncio.create_task(self._timeout())

    def reset(self):
        "return to original state, is_act() == False, done() == False, time() == 0"
        self.start_time = None
        self.end_time = None
        if self._timeout_t:
            self._timeout_t.cancel()
            self._timeout_t = None

    def stop(self):
        self.end_time = time()
        if self._timeout_t:
            self._timeout_t.cancel()
            self._timeout_t = None

    def done(self):
        if self.start_time is None:
            return False
        if self.end_time is None:
            return False
        return not self.is_act()

    def is_act(self):
        if self.start_time is None:
            return False
        if self.end_time is None:
            return (time() - self.start_time) < self.timout_s
        return False

    def time(self) -> float:
        if self.is_act():
            return 0.0
        return self.end_time - self.start_time

    def time_left(self) -> float:
        if not self.is_act():
            return 0.0
        return max(0.0, self.timout_s - (time() - self.start_time))

    def progress(self, lim=1.0) -> float:
        if self.done():
            return 1.0

        if not self.is_act():
            return 0.0

        elapsed = time() - self.start_time
        return min(lim, max(0.0, elapsed / self.timout_s))

    async def _timeout(self):
        await asyncio.sleep(self.timout_s)
        self.end_time = time()
        if self.cb:
            launch(self.cb, self.args)

    def restart(self):
        """
        Restart the timer by resetting its state and starting it again.

        This ensures the timeout starts fresh without requiring a new Timer instance.
        """
        self.reset()
        self.start()


from gui.core.colors import BLACK, RECTANGLE, GREEN, D_PINK
from gui.core.ugui import Screen
from gui.widgets.buttons import Button


def change_app(cls_new_screen, args=[], kwargs={}, base_screen=None):
    # Change to cls_new_screen. if cls_new_screen is already open back up to it
    # if cls_new_screen is not open it will be opened on top of base_screen
    # This prevents quick buttons stacking same screen over and over

    # Check stack for existing screen and change target according
    current = Screen.current_screen
    target_to_back = base_screen
    print(f"change_app: {cls_new_screen=} {target_to_back=}")
    while current and base_screen is not cls_new_screen:
        if isinstance(current, cls_new_screen):
            print(f"change_app: {cls_new_screen} already on stack")
            target_to_back = cls_new_screen
            break
        current = current.parent

    # Navigate back until reaching target_screen, then stack new app on top
    while Screen.current_screen and not isinstance(
        Screen.current_screen, target_to_back
    ):
        Screen.back()

    if cls_new_screen is target_to_back:
        # we reached BaseScreen or cls_new_screen, nothing to add
        return
    # add new screen on top of Base screen
    Screen.change(cls_new_screen, mode=Screen.STACK, args=args, kwargs=kwargs)


def fwdbutton(wri, row, col, cls_screen, text="Next"):
    def fwd(button):
        Screen.change(cls_screen)

    b = Button(
        wri,
        row,
        col,
        callback=fwd,
        fgcolor=D_PINK,
        bgcolor=BLACK,
        text=text,
        shape=RECTANGLE,
        textcolor=D_PINK,
    )
    return b.mrow


# Global button and connection handlers
# Moved from bdg/__init__.py


def handle_back(ev):
    print(f"[__Back]")
    if Screen.current_screen.parent is not None:
        Screen.back()
    else:
        print("No screen to go back to")


async def global_buttons(espnow=None, sta=None):
    from bdg.asyncbutton import ButtonEvents, ButAct
    from bdg.badge_game import GameLobbyScr
    from bdg.screens.option_screen import OptionScreen

    ev_subset = ButtonEvents.get_event_subset(
        [
            ("btn_select", ButAct.ACT_DOUBLE),
            ("btn_b", ButAct.ACT_LONG),
        ],
    )

    be = ButtonEvents(events=ev_subset)
    base_screen = GameLobbyScr

    handlers = {
        "btn_select": lambda ev: print(f"btn_select {ev}")
        or change_app(
            OptionScreen, kwargs={"espnow": espnow, "sta": sta}, base_screen=base_screen
        ),
        "btn_b": handle_back,
    }

    async for btn, ev in be.get_btn_events():
        handlers.get(btn, lambda e: print(f"Unknown {btn} {e}"))(ev)


async def new_con_cb(conn, req=False):
    """
    Handles an incoming connection request by presenting the user with a
    dialog box to accept or decline the connection.

    Only shows dialog when in GameLobbyScr or OptionScreen.
    Auto-declines when user is in other screens (games, etc).

    Handles self initiated connection if req=True
    """
    from bdg.msg.connection import Connection, NowListener
    from bdg.screens.loading_screen import LoadingScreen
    from bdg.screens.option_screen import OptionScreen
    from bdg.game_registry import get_registry
    from gui.core.writer import CWriter
    from gui.core.ugui import ssd, Screen
    from bdg.widgets.custom_dialog import CustomDialogBox
    from gui.fonts import font10
    from gui.core.colors import GREEN, BLACK, RED

    # Check if we're in an allowed screen for connection dialogs
    if not req:  # Only check for incoming connections, not self-initiated
        from bdg.badge_game import GameLobbyScr
        from bdg.screens.scan_screen import ScannerScreen, MultiplayerGameSelectionScreen
        from bdg.screens.solo_games_screen import SoloGamesScreen
        
        allowed_screens = (GameLobbyScr, OptionScreen, ScannerScreen, 
                          SoloGamesScreen, MultiplayerGameSelectionScreen)
        current = Screen.current_screen
        
        if not isinstance(current, allowed_screens):
            print(f"Connection auto-declined: User busy in {current.__class__.__name__}")
            return False  # Auto-decline

    accept = False
    if not req:
        w_reply = asyncio.Event()

        def resp(window):
            nonlocal accept
            # convert response to True
            print(f"con accept: {window.value()=}")
            accept = window.value() == "Yes"
            w_reply.set()

        wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)

        # Build a friendly label using the sender's nickname and the game title
        try:

            badge = None
            try:
                badge = NowListener.last_seen[conn.c_mac]
            except Exception:
                badge = None

            nick = None
            if badge and getattr(badge, "nick", None) is not None:
                nick = (
                    badge.nick.decode()
                    if isinstance(badge.nick, (bytes, bytearray))
                    else str(badge.nick)
                )

            registry = get_registry()
            game_config = registry.get_game(conn.con_id) if registry else None
            game_title = game_config.get("title") if game_config else f"App {conn.con_id}"

            # Build three-line label: nick / action / game
            label = f"{nick or 'Someone'}\nchallenges you to play\n{game_title}"
        except Exception:
            label = "Incoming connection"

        kwargs = {
            "writer": wri,
            "elements": (("Yes", GREEN), ("No", RED)),
            "label": label,
            "callback": resp,
        }

        # show the dialog box
        Screen.change(CustomDialogBox, kwargs=kwargs)

        try:
            # this will block until dialog callback resp() is called or timeout
            await asyncio.wait_for(w_reply.wait(), 15)
        except asyncio.TimeoutError:
            CustomDialogBox.close()  # close dialog

    if accept or req:
        # TODO: change the app that conn was opened
        # Simulate start of App
        from bdg.badge_game import GameLobbyScr

        if isinstance(Screen.current_screen, GameLobbyScr):
            # If at home screen add app on top
            mode = Screen.STACK
        else:
            # if we have other app on, replace it
            print(f"Con: Screen.REPLACE {Screen.current_screen=}")
            mode = Screen.REPLACE

        # Get game configuration from registry
        registry = get_registry()
        game_config = registry.get_game(conn.con_id)

        if game_config:
            # Build screen arguments
            screen_args = (conn,) + game_config.get("screen_args", ())

            Screen.change(
                LoadingScreen,
                mode=mode,
                kwargs={
                    "title": game_config["title"],
                    "wait": 5,
                    "nxt_scr": game_config["screen_class"],
                    "scr_args": screen_args,
                },
            )
        else:
            print(f"Warning: No game registered for con_id {conn.con_id}")

    return accept
