"""
Simple list screen base class for badge screens with title + listbox layout.

Provides common functionality for screens that display a title and a scrollable
list of items (SoloGamesScreen, MultiplayerGameSelectionScreen, etc.).
"""

from gui.core.colors import GREEN, BLACK, D_PINK
from gui.core.ugui import Screen, ssd
from gui.core.writer import CWriter
from gui.fonts import font10, freesans20
from gui.widgets.label import Label
from gui.widgets.listbox import Listbox
from bdg.widgets.hidden_active_widget import HiddenActiveWidget


class SimpleListScreen(Screen):
    """Base class for screens with title + listbox layout"""
    
    def __init__(
        self,
        title,
        elements=None,
        *,
        title_row=10,
        listbox_row=50,
        listbox_dlines=7,
        listbox_width=316,
        title_font=freesans20,
        title_color=GREEN,
        listbox_color=D_PINK,
        select_color=None,
        use_quit_widget=True,
        **kwargs
    ):
        """
        Initialize list screen with common layout.
        
        Args:
            title: Screen title text (can be updated later via set_title)
            elements: Initial list elements (strings or tuples)
            title_row: Y position for title label
            listbox_row: Y position for listbox
            listbox_dlines: Number of visible lines in listbox
            listbox_width: Width of listbox
            title_font: Font for title (default: freesans20)
            title_color: Color for title text (default: GREEN)
            listbox_color: Border color for listbox (default: D_PINK)
            select_color: Selection highlight color (default: None = DARKBLUE from micro-gui)
            use_quit_widget: Whether to add HiddenActiveWidget (default: True)
            **kwargs: Additional args passed to subclass via init_subclass()
        """
        super().__init__()
        
        # Store configuration
        self.config = {
            'title_row': title_row,
            'listbox_row': listbox_row,
            'listbox_dlines': listbox_dlines,
            'listbox_width': listbox_width,
            'title_font': title_font,
            'title_color': title_color,
            'listbox_color': listbox_color,
            'select_color': select_color if select_color is not None else listbox_color,
        }
        
        # Writers
        self.wri_title = CWriter(ssd, title_font, title_color, BLACK, verbose=False)
        self.wri_list = CWriter(ssd, font10, listbox_color, BLACK, verbose=False)
        
        # Title label
        self.lbl_title = Label(
            self.wri_title,
            title_row,
            2,
            listbox_width,
            bdcolor=False,
            justify=Label.CENTRE,
        )
        self.set_title(title)
        
        # Initialize elements
        if elements is None:
            elements = self.get_initial_elements()
        self.elements = elements if elements else [self.get_empty_message()]
        
        # Subclass-specific initialization (before listbox creation)
        self.init_subclass(**kwargs)
        
        # Listbox
        self.listbox = Listbox(
            self.wri_list,
            listbox_row,
            2,
            elements=self.elements,
            dlines=listbox_dlines,
            bdcolor=listbox_color,
            value=1,
            callback=self.on_item_selected,
            also=Listbox.ON_LEAVE,
            width=listbox_width,
        )
        
        # Quit widget
        if use_quit_widget:
            HiddenActiveWidget(self.wri_list)
    
    # Abstract methods for subclasses
    
    def get_initial_elements(self):
        """
        Get initial list elements. Override in subclass.
        
        Returns:
            List of elements (strings or tuples)
        """
        return []
    
    def get_empty_message(self):
        """
        Message to show when list is empty. Override in subclass.
        
        Returns:
            String or tuple for empty list placeholder
        """
        return "No items"
    
    def on_item_selected(self, listbox):
        """
        Called when user selects an item. Override in subclass.
        
        Args:
            listbox: The Listbox widget that triggered the callback
        """
        pass
    
    def init_subclass(self, **kwargs):
        """
        Additional initialization for subclass. Override if needed.
        Called before listbox is created, so subclasses can add widgets
        that need to be created before the listbox.
        
        Args:
            **kwargs: Additional parameters passed to __init__
        """
        pass
    
    # Helper methods
    
    def set_title(self, title):
        """Update the title text"""
        self.lbl_title.value(title)
    
    def update_list(self, elements):
        """
        Update list contents (modifies in-place for Listbox).
        
        Args:
            elements: New list of elements
        """
        self.elements.clear()
        if elements:
            self.elements.extend(elements)
        else:
            self.elements.append(self.get_empty_message())
        
        if hasattr(self, "listbox"):
            self.listbox.update()
