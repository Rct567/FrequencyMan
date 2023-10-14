from aqt import QAction, QHBoxLayout, mw as anki_main_window # type: ignore
from aqt.qt import *
from aqt.utils import showInfo
from PyQt6.QtCore import Qt 
from typing import Tuple

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
    


def create_tab_sort_cards(frequencyman_window: FrequencyManMainWindow):
    # Create a new tab and its layout
    (tab_layout, tab) = frequencyman_window.create_new_tab('sort_cards', "Sort cards")  

    # Create new target, input field for target name and button
    target_name_input = QLineEdit()
    target_name_input.setPlaceholderText("Enter target name")
    add_target_button = QPushButton("Create new target")
    create_new_target_form = QHBoxLayout()
    create_new_target_form.addWidget(target_name_input)
    create_new_target_form.addWidget(add_target_button)
    
    # Create a dynamic list for targets
    target_list = QVBoxLayout()
    target_list.setContentsMargins(2, 20, 2, 20)
    
    # Function to create a new target and add it to the list
    def create_new_target():
        new_target_name = target_name_input.text()
        target_name_input.clear()
        
        if not new_target_name:
            return
        
        # Create a new row for the target
        new_target_row_layout = QHBoxLayout()
        
        # Label to display the target name
        target_name_label = QLabel(new_target_name)
        
        # Dropdown for Anki decks
        deck_dropdown = QComboBox()
        decks = anki_main_window.col.decks.allNames() # Anki decks
        deck_dropdown.addItems(decks)
        
        # Dropdown for Anki note types
        note_type_dropdown = QComboBox()
        note_types = anki_main_window.col.models.allNames() # Anki note types
        note_type_dropdown.addItems(note_types)
        
        # Add the elements to the target row layout
        new_target_row_layout.addWidget(target_name_label)
        new_target_row_layout.addWidget(deck_dropdown)
        new_target_row_layout.addWidget(note_type_dropdown)
        
        # Add the target row to the reorder target list
        target_list.addLayout(new_target_row_layout)
        
    
    # Connect the "Add Target" button to the add_target function
    add_target_button.clicked.connect(create_new_target)
    
    # Create the "Reorder Cards" button
    reorder_cards_button = QPushButton("Reorder Cards")
    reorder_cards_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: green; color: white;")
    
    # Add all components to the main tab layout
    tab_layout.addLayout(create_new_target_form)
    tab_layout.addLayout(target_list)
    tab_layout.addWidget(reorder_cards_button)
    spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    tab_layout.addItem(spacer) # Add an empty spacer row to compress the rows above

    

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


