from typing import Any, Tuple

from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

# FrequencyMan Main Window class
class FrequencyManMainWindow(QDialog):
    
    root_dir:str
    tab_menu_options:dict[str, QWidget]
    
    addon_config:dict[str, Any]
    addon_config_write: Callable[[dict[str, Any]], None]

    def __init__(self, mw:AnkiQt):
        
        super().__init__(mw) 
        self.setWindowTitle("FrequencyMan")
        
        self.setMinimumSize(650, 600)
        
        # Create a tab widget
        self.tab_widget = QTabWidget()
        
        self.tab_menu_options = {}
        self.tab_menu_options['main'] = self.tab_widget

        # Create layout for main window/dialog, and add the tab widget to it
        window_layout = QVBoxLayout()
        window_layout.addWidget(self.tab_widget)

        # Set the layout for the main window/dialog
        self.setLayout(window_layout)
        
        # Addon config
        self.addon_config = {}
        addon_config = mw.addonManager.getConfig(__name__)
        if isinstance(addon_config, dict):
           self.addon_config = addon_config
           
        self.addon_config_write = lambda config: mw.addonManager.writeConfig(__name__, config)
        
    def create_new_tab(self, tab_id: str, tab_name: str) -> Tuple[QVBoxLayout, QWidget]:
        
        tab = QWidget()
        self.tab_menu_options[tab_id] = tab
        
        # layout for the new tab
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Add new tab to the main tab widget
        self.tab_widget.addTab(tab, tab_name)
         
        return (tab_layout, tab)