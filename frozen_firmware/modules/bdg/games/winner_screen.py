from gui.core.colors import D_PINK, WHITE, D_GREEN, BLACK
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.fonts import arial35, font10
from gui.widgets import Label, Button
import asyncio


class WinScr(Screen):
    def __init__(self, *args, **kwargs):
        super().__init__()

        self.conn = kwargs.get("conn")
        self.return_screen = kwargs.get("return_screen")

        wri = CWriter(ssd, font10, WHITE, BLACK, verbose=False)
        wrib = CWriter(ssd, arial35, D_PINK, BLACK, verbose=False)

        winner = kwargs.get("winner", "Unknown")
        message1 = kwargs.get("message1", "")
        message2 = kwargs.get("message2", "")

        Label(wri, 170 // 3 - 30, 2, 316,
              bdcolor=False, justify=1, fgcolor=D_GREEN).value("Winner is")

        Label(wrib, 170 // 3 - 10, 2, 316,
              bdcolor=False, justify=1).value(winner)

        Label(wri, 170 // 3 + 30, 2, 316,
              bdcolor=False, justify=1, fgcolor=D_GREEN).value(message1)

        Label(wri, 170 // 3 + 50, 2, 316,
              bdcolor=False, justify=1, fgcolor=D_GREEN).value(message2)



        Button(
            wri,
            row=140,
            col=100,
            width=100,
            height=24,
            text="Menu",
            callback=self.menu,
        )


    def menu(self, *args):
        # Terminate multiplayer connection before leaving
        if self.conn:
            try:
                asyncio.create_task(self.conn.terminate(send_out=True))
            except Exception as e:
                print("Failed to terminate connection:", e)

        # Correct import: ScannerScreen, not BadgeScreen
        from bdg.screens.scan_screen import ScannerScreen
        Screen.change(ScannerScreen, mode=Screen.REPLACE)
