"""Solo games selection screen - refactored to use SimpleListScreen"""

from bdg.game_registry import get_registry
from gui.core.ugui import Screen
from bdg.screens.simple_list_screen import SimpleListScreen


class SoloGamesScreen(SimpleListScreen):
    """Screen for selecting solo games and apps"""
    
    def __init__(self):
        # Load games before calling super (needed for initial elements)
        registry = get_registry()
        self.games = registry.get_solo_games()
        
        # Debug logging
        print(f"SoloGamesScreen: Found {len(self.games)} solo games")
        for game in self.games:
            print(f"  - {game['title']} (con_id={game['con_id']})")
        
        super().__init__(
            title="Solo Games & Apps",
            listbox_dlines=6,
        )
    
    def get_initial_elements(self):
        """Return list of game titles"""
        return [game["title"] for game in self.games]
    
    def get_empty_message(self):
        """Message to show when no solo games available"""
        return "No solo games available"
    
    def on_item_selected(self, listbox):
        """Launch selected game"""
        selected = listbox.textvalue()
        print(f"SoloGamesScreen: User selected '{selected}'")
        
        for game in self.games:
            if game["title"] == selected:
                screen_class = game["screen_class"]
                screen_args = game.get("screen_args", ())
                print(f"  Launching {screen_class.__name__} with args={screen_args}")
                Screen.change(
                    screen_class, 
                    args=screen_args, 
                    mode=Screen.STACK
                )
                break
        else:
            print(f"  Warning: Game '{selected}' not found in registry")
