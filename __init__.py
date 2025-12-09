"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

# mypy: disable-error-code="import-not-found"

from __future__ import annotations

from pathlib import Path

from functools import partial
from typing import Any, NamedTuple, Optional, Callable, TYPE_CHECKING

from aqt.qt import QTimer, QAction
from aqt.main import AnkiQt
from aqt import mw as anki_main_window, gui_hooks, dialogs

from anki.collection import Collection

from .frequencyman.lib.addon_config import AddonConfig
from .frequencyman.reorder_logger import LanguageInfoData, SqlDbFile, ReorderLogger

from .frequencyman.ui.words_overview_tab import WordsOverviewTab, MatureWordsOverview, WordsOverviewOption
from .frequencyman.ui.reorder_cards_tab import ReorderCardsTab
from .frequencyman.ui.main_window import FrequencyManMainWindow

if TYPE_CHECKING:
    from aqt.deckbrowser import DeckBrowser, DeckBrowserContent
    from aqt.toolbar import Toolbar
    from .frequencyman.lib.utilities import JSON_TYPE # type: ignore[import-not-found]


def get_mw():
    return anki_main_window

mw: Optional[AnkiQt] = get_mw()

FM_ROOT_DIR = Path(__file__).parent
FM_USER_FILES_DIR = FM_ROOT_DIR / 'user_files'

if not FM_USER_FILES_DIR.is_dir():
    FM_USER_FILES_DIR.mkdir()


def register_frequencyman_dialogs(mw: AnkiQt, fm_config: AddonConfig, reorder_logger: ReorderLogger) -> None:

    def dialog_creator(mw: AnkiQt) -> Optional[FrequencyManMainWindow]:
        return frequencyman_window_creator(mw, fm_config, reorder_logger)

    dialogs.register_dialog(FrequencyManMainWindow.key, dialog_creator)



def frequencyman_window_creator(mw: AnkiQt, fm_config: AddonConfig, reorder_logger: ReorderLogger) -> Optional[FrequencyManMainWindow]:

    if not isinstance(mw.col, Collection):
        return None

    fm_window = FrequencyManMainWindow(mw, mw.col, fm_config, FM_ROOT_DIR, FM_USER_FILES_DIR)
    fm_window.add_tab(ReorderCardsTab(fm_config, fm_window, mw.col, reorder_logger))
    fm_window.add_tab(WordsOverviewTab(fm_config, fm_window, mw.col))
    fm_window.show()
    return fm_window

OverviewOption = Optional[type[WordsOverviewOption]]

def open_frequencyman_word_overview(mw: AnkiQt, target_id: str, lang_id: str, overview_option: OverviewOption=None) -> None:

    fm_window: FrequencyManMainWindow = dialogs.open(FrequencyManMainWindow.key, mw)

    overview_tab = fm_window.tab_menu_options[WordsOverviewTab.id]

    if not isinstance(overview_tab, WordsOverviewTab):
        return

    overview_tab.selected_overview_option = overview_option
    overview_tab.selected_lang_id = lang_id

    if target_id != "*":
        if not overview_tab.first_paint_event_done:
            overview_tab.selected_target_by_id_str = target_id
        else:
            if (selected_target_index := overview_tab.get_target_index_by_id(target_id)) is not None:
                overview_tab.targets_dropdown.setCurrentIndex(selected_target_index)

    fm_window.show_tab(WordsOverviewTab.id)


def add_frequencyman_menu_option_to_anki_tools_menu(mw: AnkiQt):
    menu_option_title = "FrequencyMan"
    has_git_directory = (FM_ROOT_DIR / '.git').is_dir()
    if has_git_directory:
        menu_option_title += " (dev)"
    action = QAction(menu_option_title, mw)
    action.triggered.connect(lambda: dialogs.open(FrequencyManMainWindow.key, mw))
    mw.form.menuTools.addAction(action)


# get language info helper function

class InfoItem(NamedTuple):
    target_id: str
    target_display_id: str
    lang_id: str
    data: LanguageInfoData
    open_words_overview_tab: Callable[[], None]

def get_info_items_from_config(mw: AnkiQt, config: JSON_TYPE, reorder_logger: ReorderLogger, overview_option: OverviewOption=None) -> Optional[list[InfoItem]]:

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
        open_words_overview_tab = (
            lambda target_id=info_target_id, lang_id=info_lang_id, overview_option=overview_option:
            open_frequencyman_word_overview(mw, str(target_id), str(lang_id), overview_option)
        )
        info_items.append(InfoItem(info_target_id, target_display_id, info_lang_id, lang_data, open_words_overview_tab))

    reorder_logger.db.close()

    if not info_items:
        return None

    return info_items

# toolbar show_info_toolbar

def add_frequencyman_info_to_toolbar_items(mw: AnkiQt, reorder_logger: ReorderLogger, fm_config: AddonConfig) -> None:

    def init_toolbar_items(links: list[str], toolbar: Toolbar) -> None:

        if 'show_info_toolbar' not in fm_config:
            return

        info_items = get_info_items_from_config(mw, fm_config['show_info_toolbar'], reorder_logger, MatureWordsOverview)

        if info_items is None:
            return

        for info_item in info_items:
            links.append(
                toolbar.create_link(
                    cmd="fm_lang_info_toolbar_{}".format(info_item.target_id),
                    label="{}: <b>{}</b>".format(info_item.lang_id.upper(), info_item.data['num_words_mature']),
                    func=info_item.open_words_overview_tab,
                    tip="Target: {}\nLearning: {}, Mature: {}".format(info_item.target_display_id, info_item.data['num_words_learning'], info_item.data['num_words_mature']),
                    id=None,
                )
            )

    gui_hooks.top_toolbar_did_init_links.append(init_toolbar_items)

# deck browser show_info_deck_browser

def add_frequencyman_info_to_deck_browser(mw: AnkiQt, reorder_logger: ReorderLogger, fm_config: AddonConfig) -> None:

    deck_browser_open_cmds: dict[str, Callable[[], None]] = {}

    def update_deck_browser(_: DeckBrowser, content: DeckBrowserContent) -> None:

        if 'show_info_deck_browser' not in fm_config:
            return

        info_items = get_info_items_from_config(mw, fm_config['show_info_deck_browser'], reorder_logger, None)

        if info_items is None:
            return

        deck_browser_open_cmds.clear()

        content.stats += "<table cellspacing=0 cellpadding=5 style=\"min-width:340px\">"
        content.stats += "<tr style=\"text-align:left\"> <th>Language</th ><th title=\"Number of words still learning.\">Learning</th> <th title=\"Number of mature words.\">Mature</th> </tr>"
        for info_item in info_items:
            target_info = "Target: {}".format(info_item.target_display_id)
            cmd = "frequencyman_open_words_overview:{}:{}".format(info_item.target_id, info_item.lang_id)
            deck_browser_open_cmds[cmd] = info_item.open_words_overview_tab
            first_td = "<td title=\"{}\" onclick=\"return pycmd('{}')\" style=\"cursor:pointer;\">{}</td>".format(target_info, cmd, info_item.lang_id.upper())
            row_content = "{} <td>{}</td> <td><b>{}</b></td>".format(first_td, info_item.data['num_words_learning'], info_item.data['num_words_mature'])
            content.stats += "<tr>{}</tr>".format(row_content)
        content.stats += "</table>"

    gui_hooks.deck_browser_will_render_content.append(update_deck_browser)

    def handle_js_message(handled: tuple[bool, None], message: str, context: Any) -> tuple[bool, None]:
        if message in deck_browser_open_cmds:
            deck_browser_open_cmds[message]()
            return (True, None)
        return handled

    gui_hooks.webview_did_receive_js_message.append(handle_js_message)

# init FrequencyMan

if isinstance(mw, AnkiQt):

    reorder_logger = ReorderLogger(SqlDbFile(FM_USER_FILES_DIR / 'reorder_log.sqlite'))
    fm_config = AddonConfig.from_anki_main_window(mw)

    register_frequencyman_dialogs(mw, fm_config, reorder_logger)
    add_frequencyman_menu_option_to_anki_tools_menu(mw)

    add_frequencyman_info_to_deck_browser(mw, reorder_logger, fm_config)
    add_frequencyman_info_to_toolbar_items(mw, reorder_logger, fm_config)

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