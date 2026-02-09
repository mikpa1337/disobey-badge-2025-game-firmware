from gui.core.colors import GREEN, BLACK
from gui.fonts import font6, font10, font14
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.widgets import Label
import uasyncio as asyncio
from bdg.widgets.hidden_active_widget import HiddenActiveWidget


class LoadingScreen(Screen):

    def __init__(
        self,
        title: str,
        wait: int,
        nxt_scr: Screen,
        scr_args: tuple = None,
        scr_kwargs: dict = None,
        conn = None,
    ):
        super().__init__()

        self.conn = conn
        self.cancelled = False
        self.completed = False  # Track if countdown finished successfully
        self.wait_task = None
        self.listen_task = None

        wri_title = CWriter(ssd, font14, GREEN, BLACK, verbose=False)

        lbl_t = Label(wri_title, 30, 0, 320, justify=Label.CENTRE)
        lbl_t.value(text=title)

        self.wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)
        self.lbl_wait = Label(self.wri, 100, 0, 320, justify=Label.CENTRE)

        self.set_lbl_wait(wait)

        HiddenActiveWidget(self.wri)

        self.wait_task = self.reg_task(self.wait(wait, nxt_scr, scr_args, scr_kwargs))
        
        # Listen for cancellation messages from other badge
        if self.conn:
            self.listen_task = self.reg_task(self.read_messages())

    async def wait(self, wait: int, nxt_scr: Screen, scr_args: tuple, scr_kwargs: dict):
        try:
            for i in range(wait):
                if self.cancelled:
                    print("LoadingScreen: Wait cancelled by other badge")
                    return
                    
                self.set_lbl_wait(wait - i)
                await asyncio.sleep(1)

            if self.cancelled:
                print("LoadingScreen: Wait cancelled, not proceeding")
                return

            # Mark as successfully completed before transitioning
            self.completed = True
            
            if scr_args is not None:
                Screen.change(nxt_scr, mode=Screen.REPLACE, args=scr_args)
            elif scr_kwargs is not None:
                Screen.change(nxt_scr, mode=Screen.REPLACE, kwargs=scr_kwargs)
            else:
                Screen.change(nxt_scr, mode=Screen.REPLACE)
        except asyncio.CancelledError:
            print("LoadingScreen: Wait task cancelled")

    async def read_messages(self):
        """Listen for cancellation messages from other badge"""
        if not self.conn or not self.conn.active:
            print("LoadingScreen: read_messages - no active connection")
            return
            
        try:
            async for msg in self.conn.get_msg_aiter():
                print(f"LoadingScreen: Got message: {msg}")
                
                # Check msg_type attribute
                if msg.msg_type == "CancelActivityMsg":
                    print("LoadingScreen: Received cancel from other badge")
                    self.cancelled = True  # Set BEFORE Screen.back() to prevent double-send
                    self.lbl_wait.value(text="Cancelled by other badge")
                    await asyncio.sleep(1)
                    Screen.back()
                    return
                
                # Put non-cancel messages back for potential game use
                print(f"LoadingScreen: Not a cancel message ({msg.msg_type}), putting back")
                self.conn.in_q.put_nowait(msg)
        except asyncio.CancelledError:
            print("LoadingScreen: Listen task cancelled")
        except Exception as e:
            print(f"LoadingScreen: Listen error: {e}")

    def should_send_cancel(self):
        """Check if we should send cancel (user backed out, not cancelled or completed)"""
        return (not self.cancelled and 
                not self.completed and 
                self.conn and 
                self.conn.active and 
                not self.conn.closed)

    def on_hide(self):
        """Called when screen is hidden/exited - send cancellation to other badge"""
        print(f"LoadingScreen: on_hide called, cancelled={self.cancelled}, completed={self.completed}")
        
        # Cancel running tasks
        if self.wait_task:
            try:
                self.wait_task.cancel()
            except Exception:
                pass
                
        if self.listen_task:
            try:
                self.listen_task.cancel()
            except Exception:
                pass
        
        # Only send cancel if user backed out (not if countdown finished or already cancelled)
        if self.should_send_cancel():
            from bdg.msg import CancelActivityMsg
            print("LoadingScreen: Sending cancel to other badge")
            # Set cancelled BEFORE sending to prevent any race conditions
            self.cancelled = True
            try:
                msg = CancelActivityMsg()
                self.conn.send_app_msg(msg, sync=False)
            except Exception as e:
                print(f"LoadingScreen: Failed to send cancel: {e}")
        else:
            reason = "completed" if self.completed else "already cancelled" if self.cancelled else "no conn"
            print(f"LoadingScreen: Not sending cancel ({reason})")
        
        # Only terminate connection if we didn't complete successfully (game will manage it)
        if not self.completed and self.conn and not self.conn.closed:
            asyncio.create_task(self.conn.terminate(send_out=True))

    def set_lbl_wait(self, sec: int):
        self.lbl_wait.value(text=f"Starts in {sec}..")
