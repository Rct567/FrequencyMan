"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from functools import partial
from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

from anki.collection import Collection
from aqt.utils import showInfo, askUser, showWarning

from .frequencyman.target_reorder_logger import TargetReorderLogger

from .frequencyman.ui.overview_tab import OverviewTab
from .frequencyman.ui.reorder_cards_tab import ReorderCardsTab
from .frequencyman.ui.main_window import FrequencyManMainWindow

from .frequencyman.lib.utilities import *

from aqt import mw, gui_hooks
from aqt.utils import tooltip


def get_mw():
    return mw

mw: Optional[AnkiQt] = get_mw()

FM_ROOT_DIR = os.path.dirname(__file__)
FM_USER_FILES_DIR = os.path.join(FM_ROOT_DIR, 'user_files')

if not os.path.isdir(FM_USER_FILES_DIR):
    os.mkdir(FM_USER_FILES_DIR)

reorder_logger = TargetReorderLogger(os.path.join(FM_USER_FILES_DIR, 'reorder_log.sqlite'))

# menu option to main window

def open_frequencyman_main_window(mw: AnkiQt):
    if not isinstance(mw.col, Collection):
        return

    fm_window = FrequencyManMainWindow(mw, FM_ROOT_DIR, FM_USER_FILES_DIR)

    fm_window.add_tab(ReorderCardsTab(fm_window, mw.col, reorder_logger))
    #fm_window.add_tab(OverviewTab(fm_window))

    fm_window.exec()


def add_frequencyman_menu_option_to_anki_tools_menu(mw: AnkiQt):
    action = QAction("FrequencyMan", mw)
    action.triggered.connect(lambda: open_frequencyman_main_window(mw))
    mw.form.menuTools.addAction(action)

# toolbar

def add_frequencyman_to_toolbar_items(reorder_logger: TargetReorderLogger) -> None:

    from aqt.toolbar import Toolbar

    def init_toolbar_items(reorder_logger: TargetReorderLogger, links: list[str], toolbar: Toolbar) -> None:

        for info in reorder_logger.get_latest_reorder_info():

            links.append(
                toolbar.create_link(
                    cmd="fm_lang_info_toolbar",
                    label="{}: <b>{}</b>".format(info['lang_id'].upper(), info['num_word_mature']),
                    func=lambda: None,
                    tip=None,
                    id=None,
                )
            )

    gui_hooks.top_toolbar_did_init_links.append(partial(init_toolbar_items, reorder_logger))


# deck browser

def add_frequencyman_info_to_deck_browser(reorder_logger: TargetReorderLogger) -> None:

    from aqt.deckbrowser import DeckBrowser

    if TYPE_CHECKING:
        from aqt.deckbrowser import DeckBrowserContent

    def update_deck_browser(reorder_logger: TargetReorderLogger, deck_browser: DeckBrowser, content: "DeckBrowserContent") -> None:

        for info in reorder_logger.get_latest_reorder_info():

            content.stats += "<p>{}: <b>{}</b></p>".format(info['lang_id'].upper(), info['num_word_mature'])

    gui_hooks.deck_browser_will_render_content.append(partial(update_deck_browser, reorder_logger))

# init all

if isinstance(mw, AnkiQt):
    add_frequencyman_menu_option_to_anki_tools_menu(mw)
    #add_frequencyman_info_to_deck_browser(reorder_logger)
    #add_frequencyman_to_toolbar_items(reorder_logger)