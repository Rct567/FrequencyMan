from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

from anki.collection import Collection
from aqt.utils import showInfo, askUser, showWarning

from .frequencyman.ui.overview_tab import OverviewTab
from .frequencyman.ui.reorder_cards_tab import ReorderCardsTab
from .frequencyman.ui.main_window import FrequencyManMainWindow

from .frequencyman.lib.utilities import *

def get_mw():
    from aqt import mw # type: ignore
    return mw

mw:AnkiQt = get_mw()
     
# Open 'FrequencyMan main window' and create tabs
def open_frequencyman_main_window(mw:AnkiQt):
    
    if not isinstance(mw.col, Collection):
        return
    
    fm_window = FrequencyManMainWindow(mw)
    
    fm_window.root_dir = os.path.dirname(__file__)
    
    ReorderCardsTab.create_new_tab(fm_window, mw.col);
    OverviewTab.create_new_tab(fm_window);
    
    fm_window.exec()


# Add "FrequencyMan" menu option in the "Tools" menu of the main Anki window 
def add_frequencyman_menu_option_to_anki_tools_menu(mw:AnkiQt):
    action = QAction("FrequencyMan", mw)
    action.triggered.connect(lambda: open_frequencyman_main_window(mw))
    mw.form.menuTools.addAction(action)

if isinstance(mw, AnkiQt):
    add_frequencyman_menu_option_to_anki_tools_menu(mw)


