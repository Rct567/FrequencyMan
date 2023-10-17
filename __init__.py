from ast import dump
import json
from aqt import QAction, QHBoxLayout, mw as anki_main_window # type: ignore
from aqt.qt import *
from aqt.utils import showInfo
from PyQt6.QtCore import Qt 
from typing import Tuple


def dump_var(var):
    showInfo(str(var))
    showInfo(repr(var))


# FrequencyMan Main Window class
class FrequencyManMainWindow(QDialog):
    def __init__(self):
        super().__init__(anki_main_window) 
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
        
        self.config = anki_main_window.addonManager.getConfig(__name__)
        
    def create_new_tab(self, tab_id: str, tab_name: str) -> Tuple[QVBoxLayout, QWidget]:
        tab = QWidget()
        self.tab_menu_options[tab_id] = tab
        
        # layout for the new tab
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Add new tab to the main tab widget
        self.tab_widget.addTab(tab, tab_name)
         
        return (tab_layout, tab)
    

def validate_target_data(json_data: str) -> int:
    try:
        data:dict = json.loads(json_data)
        if type(data) is dict and data.get("fm_reorder_target"):
            return 1
        return 0
    except json.JSONDecodeError:
        return -1

def create_tab_sort_cards(frequencyman_window: FrequencyManMainWindow):
    # Create a new tab and its layout
    (tab_layout, tab) = frequencyman_window.create_new_tab('sort_cards', "Sort cards")

    # Create a QTextEdit widget for the JSON textarea
    target_data_textarea = QTextEdit()
    target_data_textarea.setAcceptRichText(False)

     # Function to check if the JSON is valid
    def check_json_validity():
        validity_state = validate_target_data(target_data_textarea.toPlainText());
        palette = QPalette()
        if (validity_state == 1):
            palette.setColor(QPalette.ColorRole.Text, QColor(Qt.GlobalColor.green)) 
        if (validity_state == -1):
            palette.setColor(QPalette.ColorRole.Text, QColor(Qt.GlobalColor.red)) 
        target_data_textarea.setPalette(palette)   
        

    # Connect the check_json_validity function to textChanged signal
    target_data_textarea.textChanged.connect(check_json_validity)

    # Create the "Reorder Cards" button
    reorder_cards_button = QPushButton("Reorder Cards")
    reorder_cards_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: green; color: white;")
    
    tab_layout.addWidget(target_data_textarea)
    tab_layout.addWidget(reorder_cards_button)
    tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)) # Add an empty spacer row to compress the rows above
    

def create_tab_word_overview(frequencyman_window: FrequencyManMainWindow):
    (tab_layout, tab) = frequencyman_window.create_new_tab('word_overview', "Word overview")
    # Create a label to display "Test" in the panel
    label = QLabel("** Overview of easy and hard words....")
    tab_layout.addWidget(label)

     
# Open the 'FrequencyMan main window'
def open_frequencyman_main_window():
    frequencyman_window = FrequencyManMainWindow()
    create_tab_sort_cards(frequencyman_window);
    create_tab_word_overview(frequencyman_window);
    frequencyman_window.exec_()


# Add "FrequencyMan" menu option in the "Tools" menu of the main Anki window
def add_frequencyman_menu_option_to_anki_tools_menu():
    action = QAction("FrequencyMan", anki_main_window)
    action.triggered.connect(open_frequencyman_main_window)
    anki_main_window.form.menuTools.addAction(action)


# Main components
add_frequencyman_menu_option_to_anki_tools_menu()


