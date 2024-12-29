"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from functools import partial
from typing import NamedTuple

from aqt import QAction
from aqt.qt import QTimer
from aqt.main import AnkiQt
from aqt.utils import showInfo, askUser, showWarning

from anki.collection import Collection

from .frequencyman.lib.addon_config import AddonConfig
from .frequencyman.reorder_logger import LanguageInfoData, ReorderLogger

from .frequencyman.ui.words_overview_tab import WordsOverviewTab
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

def open_frequencyman_main_window(mw: AnkiQt, addon_config: AddonConfig, reorder_logger: ReorderLogger):
    if not isinstance(mw.col, Collection):
        return

    fm_window = FrequencyManMainWindow(mw, mw.col, addon_config, FM_ROOT_DIR, FM_USER_FILES_DIR)

    fm_window.add_tab(ReorderCardsTab(fm_window, mw.col, reorder_logger))
    fm_window.add_tab(WordsOverviewTab(fm_window, mw.col))

    fm_window.show()

def add_frequencyman_menu_option_to_anki_tools_menu(mw: AnkiQt, addon_config: AddonConfig, reorder_logger: ReorderLogger):
    menu_option_title = "FrequencyMan"
    has_git_directory = os.path.isdir(os.path.join(FM_ROOT_DIR, '.git'))
    if has_git_directory:
        menu_option_title += " (dev)"
    action = QAction(menu_option_title, mw)
    action.triggered.connect(lambda: open_frequencyman_main_window(mw, addon_config, reorder_logger))
    mw.form.menuTools.addAction(action)

# get language info helper function

class InfoItem(NamedTuple):
    target_id: str
    target_display_id: str
    lang_id: str
    data: LanguageInfoData

def get_info_items_from_config(config: JSON_TYPE, reorder_logger: ReorderLogger) -> Optional[list[InfoItem]]:

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

        target_display_id = "Global (all logged targets)" if info_target_id == "*" else info_target_id
        info_items.append(InfoItem(info_target_id, target_display_id, info_lang_id, lang_data))

    if not info_items:
        return None

    return info_items

# toolbar show_info_toolbar

def add_frequencyman_info_to_toolbar_items(reorder_logger: ReorderLogger, fm_config: AddonConfig) -> None:

    from aqt.toolbar import Toolbar

    def init_toolbar_items(links: list[str], toolbar: Toolbar) -> None:

        if 'show_info_toolbar' not in fm_config:
            return

        info_items = get_info_items_from_config(fm_config['show_info_toolbar'], reorder_logger)

        if info_items is None:
            return

        for info_item in info_items:
            links.append(
                toolbar.create_link(
                    cmd="fm_lang_info_toolbar_{}".format(info_item.target_id),
                    label="{}: <b>{}</b>".format(info_item.lang_id.upper(), info_item.data['num_words_mature']),
                    func=lambda: None,
                    tip="Target: {}\nLearning: {}, Mature: {}".format(info_item.target_display_id, info_item.data['num_words_learning'], info_item.data['num_words_mature']),
                    id=None,
                )
            )

    gui_hooks.top_toolbar_did_init_links.append(init_toolbar_items)

# deck browser show_info_deck_browser

def add_frequencyman_info_to_deck_browser(reorder_logger: ReorderLogger, fm_config: AddonConfig) -> None:

    from aqt.deckbrowser import DeckBrowser

    if TYPE_CHECKING:
        from aqt.deckbrowser import DeckBrowserContent

    def update_deck_browser(deck_browser: DeckBrowser, content: "DeckBrowserContent") -> None:

        if 'show_info_deck_browser' not in fm_config:
            return

        info_items = get_info_items_from_config(fm_config['show_info_deck_browser'], reorder_logger)

        if info_items is None:
            return

        content.stats += "<table cellspacing=0 cellpadding=5 style=\"min-width:340px\">"
        content.stats += "<tr style=\"text-align:left\"> <th>Language</th ><th title=\"Number of words still learning.\">Learning</th> <th title=\"Number of mature words.\">Mature</th> </tr>"
        for info_item in info_items:
            target_info = "Target: {}".format(info_item.target_display_id)
            row_content = "<td title=\"{}\">{}</td> <td>{}</td> <td><b>{}</b></td>".format(target_info, info_item.lang_id.upper(), info_item.data['num_words_learning'], info_item.data['num_words_mature'])
            content.stats += "<tr>{}</tr>".format(row_content)
        content.stats += "</table>"

    gui_hooks.deck_browser_will_render_content.append(update_deck_browser)

# init FrequencyMan

if isinstance(mw, AnkiQt):

    reorder_logger = ReorderLogger(os.path.join(FM_USER_FILES_DIR, 'reorder_log.sqlite'))
    fm_config = AddonConfig.from_anki_main_window(mw)

    add_frequencyman_menu_option_to_anki_tools_menu(mw, fm_config, reorder_logger)

    add_frequencyman_info_to_deck_browser(reorder_logger, fm_config)
    add_frequencyman_info_to_toolbar_items(reorder_logger, fm_config)

    # handle config editor (reload info elements after config is saved)

    def reload_info_elements(fm_config: AddonConfig, mw: AnkiQt) -> None:
        fm_config.reload()
        mw.deckBrowser.refresh()
        mw.toolbar.draw()

    def handle_addon_config_editor_update(mw: AnkiQt, fm_config: AddonConfig, text: str, addon: str) -> str:
        if addon != __name__:
            return text
        QTimer.singleShot(800, partial(reload_info_elements, fm_config, mw))  # wait for config to be saved
        return text


    gui_hooks.addon_config_editor_will_update_json.append(partial(handle_addon_config_editor_update, mw, fm_config))