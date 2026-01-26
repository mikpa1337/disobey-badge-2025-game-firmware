import asyncio

from bdg.msg import BadgeAdr, null_badge_adr
from bdg.msg.connection import NowListener, Beacon
from bdg.game_registry import get_registry
from bdg.widgets.hidden_active_widget import HiddenActiveWidget
from gui.core.colors import GREEN, BLACK, D_PINK
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.fonts import font10, freesans20
from gui.primitives import launch
from gui.widgets.label import Label
from gui.widgets.listbox import Listbox, dolittle
from bdg.screens.simple_list_screen import SimpleListScreen


class MultiplayerGameSelectionScreen(SimpleListScreen):
    """Screen for selecting multiplayer game with a badge"""
    
    def __init__(self, badge_addr: BadgeAdr = null_badge_adr):
        self.baddr = badge_addr
        
        # Load games before calling super
        registry = get_registry()
        self.games = registry.get_all_games()
        
        super().__init__(
            title=f"Challenge: {badge_addr.nick}",
            listbox_dlines=6,
        )
    
    def init_subclass(self, **kwargs):
        """Add status label for connection feedback"""
        wri_status = CWriter(ssd, font10, GREEN, BLACK, verbose=False)
        self.s_lbl = Label(
            wri_status, 35, 2, 316, bdcolor=False, justify=Label.CENTRE
        )
    
    def get_initial_elements(self):
        """Return list of multiplayer game titles"""
        games = [
            game["title"] for game in self.games 
            if game.get("multiplayer", False)
        ]
        return games if games else None
    
    def get_empty_message(self):
        """Message to show when no multiplayer games available"""
        return "No multiplayer games available"
    
    def on_item_selected(self, listbox):
        """Launch selected game"""
        game_title = listbox.textvalue()
        
        for game in self.games:
            if game["title"] == game_title:
                con_id = game["con_id"]
                print(f"Connecting to {game_title} (con_id={con_id})")
                self.s_lbl.value("Connecting...")
                launch(self.launch_app, (con_id,))
                break
        else:
            print(f"Unknown game: {game_title}")
        
        print("lbcb!!!")
    
    async def launch_app(self, app_id):
        """Launch multiplayer game with connection"""
        if not await NowListener.conn_req(self.baddr.mac, app_id):
            self.s_lbl.value("Con failed!")


class ScannerScreen(Screen):
    """Simple scanner draft that start EspNowScanner and display results in a listbox"""

    def __init__(self, espnow=None, sta=None):
        super().__init__()
        self.espnow = espnow
        self.update_task = None
        self.max_badges = NowListener.last_seen.max_size
        
        # Title writer with freesans20 font
        wri = CWriter(ssd, freesans20, GREEN, BLACK, verbose=False)
        # Listbox writer with font10 and D_PINK
        wri_pink = CWriter(ssd, font10, D_PINK, BLACK, verbose=False)

        # Title label centered at top
        self.lbl_title = Label(
            wri,
            10,
            2,
            316,
            bdcolor=False,
            justify=Label.CENTRE,
        )
        self.lbl_title.value(f"{self.max_badges} near badges")

        # Initialize with placeholder
        self.elements = [("No badges found, looking..", dolittle, (null_badge_adr,))]
        self.listbox = Listbox(
            wri_pink,
            50,
            2,
            elements=self.elements,
            dlines=6,
            bdcolor=D_PINK,
            also=Listbox.ON_LEAVE,
            width=316,
        )

        HiddenActiveWidget(wri_pink)  # Quit the application

    def cb(self, *args):

        Screen.change(MultiplayerGameSelectionScreen, args=(args[1],))

    def on_open(self):
        # TODO: README This is the only way to add workers to task!!
        # if reg_task() is called in init task will not be restarted when coming
        # back from dialog of dropdown
        if not self.update_task or self.update_task.done():
            self.update_task = self.reg_task(self.update_resuls_task(), True)

    def rebuild_list(self):
        """Rebuild the badge list from NowListener.last_seen."""
        
        # Get all current badges from NowListener
        current_badges = list(NowListener.last_seen.values())
        
        # Clear the existing list (modifying in place)
        self.elements.clear()
        
        if not current_badges:
            # No badges found, show placeholder
            self.elements.append(("No badges found, looking..", dolittle, (null_badge_adr,)))
        else:
            # Build new elements from current badges
            new_elements = [
                (
                    f"{badge.nick} [{badge.rssi}dBm]",
                    self.cb,
                    (badge,),
                )
                for badge in current_badges
            ]
            # Sort alphabetically by nickname (case-insensitive)
            new_elements.sort(key=lambda a: a[2][0].nick.lower())
            
            # Add sorted elements to the list
            self.elements.extend(new_elements)
        
        # Update listbox display
        if hasattr(self, "listbox"):
            self.listbox.update()

    async def update_resuls_task(self):
        try:
            NowListener.start(self.espnow)  # ensure scanner is running
            Beacon.suspend(False)  # ensure that we have beacon on

            # initial update - rebuild entire list
            self.rebuild_list()

            # wait for changes (both additions and removals)
            async for latest_badge in NowListener.updates():
                # Rebuild entire list on any change
                # This handles both additions and removals (from cleanup_stale)
                self.rebuild_list()
                await asyncio.sleep(0)
        except Exception as e:
            print(f"update_resuls_task: {e}")
