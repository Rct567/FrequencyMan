"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

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
    from aqt import mw  # type: ignore

    return mw


mw: Optional[AnkiQt] = get_mw()


# Open 'FrequencyMan main window' and create tabs
def open_frequencyman_main_window(mw: AnkiQt):
    if not isinstance(mw.col, Collection):
        return

    root_dir = os.path.dirname(__file__)
    user_files_dir = os.path.join(root_dir, 'user_files')

    if not os.path.isdir(user_files_dir):
        showWarning("Directory 'user_files' not found in {}.".format(root_dir))
        return

    fm_window = FrequencyManMainWindow(mw, root_dir, user_files_dir)

    ReorderCardsTab(fm_window, mw.col).create_new_tab()
    #OverviewTab(fm_window).create_new_tab()

    fm_window.exec()


# Add "FrequencyMan" menu option in the "Tools" menu of the main Anki window
def add_frequencyman_menu_option_to_anki_tools_menu(mw: AnkiQt):
    action = QAction("FrequencyMan", mw)
    action.triggered.connect(lambda: open_frequencyman_main_window(mw))
    mw.form.menuTools.addAction(action)


if isinstance(mw, AnkiQt):
    add_frequencyman_menu_option_to_anki_tools_menu(mw)
