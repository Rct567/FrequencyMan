import json
from aqt import QAction, mw as anki_main_window # type: ignore
from aqt.qt import *
from aqt.utils import showInfo
from typing import List, Optional, Tuple
import pprint

def dump_var(var):
    #showInfo(str(var))
    showInfo(pprint.pformat(var))


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
        
        self.fm_config:dict = anki_main_window.addonManager.getConfig(__name__)
        
    def create_new_tab(self, tab_id: str, tab_name: str) -> Tuple[QVBoxLayout, QWidget]:
        tab = QWidget()
        self.tab_menu_options[tab_id] = tab
        
        # layout for the new tab
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Add new tab to the main tab widget
        self.tab_widget.addTab(tab, tab_name)
         
        return (tab_layout, tab)
  
def validate_target_data(target_data: list) -> int: 
    if len(target_data) < 1:
        return 0
    for target in target_data:
        if type(target) != dict or len(target.keys()) == 0:
            return 0
        for key in target.keys():
            if key not in ("deck", "notes"):
                return 0
    return 1

def validate_json_target_data(json_data: str) -> Tuple[int, Optional[List]]:
    try:
        data:list = json.loads(json_data)
        if type(data) == list:
            return (validate_target_data(data), data)
        return (-1, None)
    except json.JSONDecodeError:
        return (-1, None)
    
def execute_reorder(target_data_textarea: QTextEdit):
    showInfo("Reordering!")
    (validity_state, data) = validate_json_target_data(target_data_textarea.toPlainText());
    if validity_state == -1:
        showInfo('JSON Format is not valid. Fail to parse JSON.')
    elif validity_state == 0:
        showInfo('Target data is not valid. Check necessary such as "deck" and "notes" keys are present.')
    

def create_tab_sort_cards(fm_window: FrequencyManMainWindow):
    # Create a new tab and its layout
    (tab_layout, tab) = fm_window.create_new_tab('sort_cards', "Sort cards")

    # Create textarea widget
    target_data_textarea = QTextEdit()
    target_data_textarea.setMinimumHeight(300);
    target_data_textarea.setAcceptRichText(False)
    target_data_textarea.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2;")
        
    # Set 'reorder target data from plugin config file' as json in textarea
    if fm_window.fm_config and "fm_reorder_target" in fm_window.fm_config:
        target_data_textarea.setText(json.dumps(fm_window.fm_config.get("fm_reorder_target"), indent=4))
    
    # Check if the JSON and target data is valid
    def check_textarea_json_validity():
        (validity_state, _) = validate_json_target_data(target_data_textarea.toPlainText());
        palette = QPalette()
        if (validity_state == 1):
            palette.setColor(QPalette.ColorRole.Text, QColor("#23b442")) # Green
        if (validity_state == -1):
            palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c")) # Red
        target_data_textarea.setPalette(palette)   

    # Connect the check_json_validity function to textChanged signal
    target_data_textarea.textChanged.connect(check_textarea_json_validity)
    check_textarea_json_validity()

    # Create the "Reorder Cards" button
    exec_reorder_button = QPushButton("Reorder Cards")
    exec_reorder_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #23b442; color: white; border:2px solid #23a03e")
    exec_reorder_button.clicked.connect(lambda: execute_reorder(target_data_textarea))
    
    tab_layout.addWidget(target_data_textarea)
    tab_layout.addWidget(exec_reorder_button)
    tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)) # Add an empty spacer row to compress the rows above
    

def create_tab_word_overview(fm_window: FrequencyManMainWindow):
    (tab_layout, tab) = fm_window.create_new_tab('word_overview', "Word overview")
    # Create a label to display "Test" in the panel
    label = QLabel("** Overview of easy and hard words....")
    tab_layout.addWidget(label)

     
# Open the 'FrequencyMan main window'
def open_frequencyman_main_window():
    fm_window = FrequencyManMainWindow()
    create_tab_sort_cards(fm_window);
    create_tab_word_overview(fm_window);
    fm_window.exec()


# Add "FrequencyMan" menu option in the "Tools" menu of the main Anki window
def add_frequencyman_menu_option_to_anki_tools_menu():
    action = QAction("FrequencyMan", anki_main_window)
    action.triggered.connect(open_frequencyman_main_window)
    anki_main_window.form.menuTools.addAction(action)


# Main components
add_frequencyman_menu_option_to_anki_tools_menu()


