"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import NamedTuple
from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

from anki.collection import Collection
from aqt.utils import showInfo, askUser, showWarning

from .frequencyman.lib.addon_config import AddonConfig
from .frequencyman.target_reorder_logger import LanguageInfoData, TargetReorderLogger

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

# add menu option to main window

def open_frequencyman_main_window(mw: AnkiQt, addon_config: AddonConfig):
    if not isinstance(mw.col, Collection):
        return

    fm_window = FrequencyManMainWindow(mw, addon_config, FM_ROOT_DIR, FM_USER_FILES_DIR)

    fm_window.add_tab(ReorderCardsTab(fm_window, mw.col, reorder_logger))
    #fm_window.add_tab(OverviewTab(fm_window))

    fm_window.exec()


def add_frequencyman_menu_option_to_anki_tools_menu(mw: AnkiQt, addon_config: AddonConfig):
    action = QAction("FrequencyMan", mw)
    action.triggered.connect(lambda: open_frequencyman_main_window(mw, addon_config))
    mw.form.menuTools.addAction(action)

# get language info helper function

class InfoItem(NamedTuple):
    target_id: str
    lang_id: str
    data: LanguageInfoData

def get_info_items_from_config(config: JSON_TYPE, reorder_logger: TargetReorderLogger) -> Optional[list[InfoItem]]:

    info_items: list[InfoItem] = []

    if not isinstance(config, list) or not all(isinstance(info, dict) for info in config):
        return

    for info_item in config:

        if not isinstance(info_item, dict):
            continue
        if 'target' not in info_item or 'lang' not in info_item:
            continue

        info_target_id = info_item['target']
        info_lang_id = info_item['lang']

        if not isinstance(info_target_id, str) or not isinstance(info_lang_id, str):
            continue

        try:
            if info_target_id == '*':
                lang_data = reorder_logger.get_info_global()[info_lang_id.lower()]
            else:
                lang_data = reorder_logger.get_info_per_target()[info_target_id][info_lang_id.lower()]
        except KeyError:
            continue

        info_items.append(InfoItem(info_target_id, info_lang_id, lang_data))

    if not info_items:
        return None

    return info_items

# toolbar show_info_toolbar

def add_frequencyman_to_toolbar_items(reorder_logger: TargetReorderLogger, fm_config: AddonConfig) -> None:

    from aqt.toolbar import Toolbar

    def init_toolbar_items(links: list[str], toolbar: Toolbar) -> None:

        info_items = get_info_items_from_config(fm_config['show_info_toolbar'], reorder_logger)

        if info_items is None:
            return

        for info_item in info_items:
            links.append(
                toolbar.create_link(
                    cmd="fm_lang_info_toolbar",
                    label="{}: <b>{}</b>".format(info_item.lang_id.upper(), info_item.data['num_words_mature']),
                    func=lambda: None,
                    tip=None,
                    id=None,
                )
            )

    gui_hooks.top_toolbar_did_init_links.append(init_toolbar_items)

# deck browser show_info_deck_browser

def add_frequencyman_info_to_deck_browser(reorder_logger: TargetReorderLogger, fm_config: AddonConfig) -> None:

    from aqt.deckbrowser import DeckBrowser

    if TYPE_CHECKING:
        from aqt.deckbrowser import DeckBrowserContent

    def update_deck_browser(deck_browser: DeckBrowser, content: "DeckBrowserContent") -> None:

        info_items = get_info_items_from_config(fm_config['show_info_deck_browser'], reorder_logger)

        if info_items is None:
            return

        content.stats += "<table cellspacing=0 cellpadding=5>"
        content.stats += "<tr> <th>Language</th ><th>Learning words</th> <th>Mature words</th> </tr>"
        for info_item in info_items:
            content.stats += "<tr> <td>{}</td> <td>{}</td> <td><b>{}</b></td> </tr>".format(info_item.lang_id.upper(), info_item.data['num_words_learning'], info_item.data['num_words_mature'])
        content.stats += "</table>"

    gui_hooks.deck_browser_will_render_content.append(update_deck_browser)

# init all

if isinstance(mw, AnkiQt):

    reorder_logger = TargetReorderLogger(os.path.join(FM_USER_FILES_DIR, 'reorder_log.sqlite'))

    addon_manager = mw.addonManager

    current_config = addon_manager.getConfig(__name__)
    config_writer: Callable[[dict[str, Any]], None] = lambda config: addon_manager.writeConfig(__name__, config)

    if current_config is None:
        current_config = {}

    fm_config = AddonConfig(current_config, config_writer)

    add_frequencyman_menu_option_to_anki_tools_menu(mw, fm_config)
    if 'show_info_deck_browser' in fm_config:
        add_frequencyman_info_to_deck_browser(reorder_logger, fm_config)
    if 'show_info_toolbar' in fm_config:
        add_frequencyman_to_toolbar_items(reorder_logger, fm_config)