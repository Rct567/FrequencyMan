"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import UserString, defaultdict
import importlib
import os
import sys
from typing import Callable, Optional


class LangId(UserString):

    def __init__(self, lang_id: str) -> None:
        assert len(lang_id) == 2, "Two characters only for LangId!"
        assert lang_id.isalpha(), "Only alphabetic characters for LangId!"
        assert lang_id.islower(), "Lowercase only for LangId!"
        super().__init__(lang_id)


Tokenizer = Callable[[str], list[str]]


class Tokenizers:

    tokenizers: dict[LangId, list[Tokenizer]]
    tokenizers_hashes: set[int]

    def __init__(self) -> None:
        self.tokenizers = defaultdict(list)
        self.tokenizers_hashes = set()

    def register(self, lang_id: LangId, tokenizer: Tokenizer) -> None:

        if hash(tokenizer) in self.tokenizers_hashes:
            raise ValueError("Tokenizer '{}' already registered!".format(tokenizer.__name__))

        self.tokenizers[lang_id].append(tokenizer)
        self.tokenizers_hashes.add(hash(tokenizer))

    def get_tokenizer(self, lang_id: LangId) -> Tokenizer:

        return self.tokenizers[lang_id][0]

    def get_all_tokenizers(self, lang_id: LangId) -> list[Tokenizer]:

        return self.tokenizers[lang_id]

    def lang_has_tokenizer(self, lang_id: LangId) -> bool:

        if lang_id not in self.tokenizers:
            return False

        return len(self.tokenizers[lang_id]) > 0


LOADED_USER_PROVIDED_TOKENIZERS: Optional[Tokenizers] = None


def load_user_provided_tokenizers() -> Tokenizers:

    global LOADED_USER_PROVIDED_TOKENIZERS

    if LOADED_USER_PROVIDED_TOKENIZERS is not None:
        return LOADED_USER_PROVIDED_TOKENIZERS

    fm_plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    anki_plugins_dir = os.path.abspath(os.path.join(fm_plugin_root, '..'))
    tokenizers_user_dir = os.path.join(fm_plugin_root, 'user_files', 'tokenizers')

    if not os.path.exists(anki_plugins_dir):
        raise Exception("Could not find anki plugin directory!")

    LOADED_USER_PROVIDED_TOKENIZERS = Tokenizers()

    # load custom defined tokenizers from user_files directory

    if os.path.exists(tokenizers_user_dir):

        for sub_dir in os.listdir(tokenizers_user_dir):

            tokenizer_dir = os.path.join(tokenizers_user_dir, sub_dir)

            if not os.path.isdir(tokenizer_dir):
                continue

            tokenizer_id = None

            for filename in os.listdir(tokenizer_dir):
                if filename.startswith('fm_init_') and filename.endswith('.py'):
                    tokenizer_id = filename.replace('fm_init_', '').replace('.py', '')
                    break

            if tokenizer_id is None:
                continue

            if not os.path.isdir(os.path.join(tokenizer_dir, tokenizer_id)):
                raise Exception("Tokenizer subdirectory '{}' does not exist in '{}'.".format(tokenizer_id, tokenizer_dir))

            tokenizer_init_module_name = 'fm_init_'+tokenizer_id

            sys.path.append(tokenizer_dir)
            module = importlib.import_module(tokenizer_init_module_name, tokenizer_dir)
            tokenizers_provider: Callable[[], list[tuple[str, Tokenizer]]] = getattr(module, tokenizer_id+'_tokenizers_provider')

            for lang_id, tokenizer in tokenizers_provider():

                if not isinstance(lang_id, str) or len(lang_id) != 2:
                    raise Exception("Invalid lang_id given by '{}' in '{}'.".format(tokenizers_provider.__name__, tokenizer_dir))

                LOADED_USER_PROVIDED_TOKENIZERS.register(LangId(lang_id), tokenizer)

    # ankimorphs-chinese-jieba plugin (companion add-on for AnkiMorphs)

    jieba_anki_morphs_plugin_path = os.path.join(anki_plugins_dir, '1857311956')

    if os.path.exists(jieba_anki_morphs_plugin_path):

        sys.path.append(jieba_anki_morphs_plugin_path)
        jieba_anki_morphs_module = importlib.import_module("jieba.posseg")

        def anki_morphs_jieba_tokenizer(txt: str) -> list[str]:
            return list(token for (token, _) in jieba_anki_morphs_module.lcut(txt) if token is not None)

        LOADED_USER_PROVIDED_TOKENIZERS.register(LangId('zh'), anki_morphs_jieba_tokenizer)

    # ankimorphs-japanese-mecab plugin (companion add-on for AnkiMorphs)

    mecab_anki_morphs_plugin_path = os.path.join(anki_plugins_dir, '1974309724')

    if os.path.exists(mecab_anki_morphs_plugin_path):

        sys.path.append(anki_plugins_dir)
        mecab_anki_morphs_module = importlib.import_module("1974309724.reading")

        from .anki_morphs_mecab_wrapper import setup_mecab, get_morphemes_mecab

        setup_mecab(mecab_anki_morphs_module)

        def anki_morphs_mecab_tokenizer(expression: str) -> list[str]:
            return get_morphemes_mecab(expression)

        LOADED_USER_PROVIDED_TOKENIZERS.register(LangId('ja'), anki_morphs_mecab_tokenizer)

    # mecab tokenizer from 'ajt japanese' plugin

    ajt_japanese_plugin_path = os.path.join(anki_plugins_dir, '1344485230')

    if os.path.exists(ajt_japanese_plugin_path):

        sys.path.append(ajt_japanese_plugin_path)
        ajt_japanese_module = importlib.import_module('mecab_controller.mecab_controller')

        mecab = ajt_japanese_module.MecabController(verbose=False)

        def ajt_japanese_mecab_tokenizer(txt: str) -> list[str]:
            return [token.word for token in mecab.translate(txt)]

        LOADED_USER_PROVIDED_TOKENIZERS.register(LangId('ja'), ajt_japanese_mecab_tokenizer)

    #  mecab and jieba tokenizer from 'morphman' plugin

    morphman_plugin_path = os.path.join(anki_plugins_dir, '900801631')

    if os.path.exists(morphman_plugin_path):

        sys.path.append(morphman_plugin_path)
        morphemizer_module = importlib.import_module('morph.morphemizer')

        morphemizer_mecab = morphemizer_module.getMorphemizerByName("MecabMorphemizer")

        def morphman_mecab_tokenizer(txt: str) -> list[str]:
            return [token.base for token in morphemizer_mecab.getMorphemesFromExpr(txt)]

        LOADED_USER_PROVIDED_TOKENIZERS.register(LangId('ja'), morphman_mecab_tokenizer)

        morphemizer_jieba = morphemizer_module.getMorphemizerByName("JiebaMorphemizer")

        def morphman_jieba_tokenizer(txt: str) -> list[str]:
            return [token.base for token in morphemizer_jieba.getMorphemesFromExpr(txt)]

        LOADED_USER_PROVIDED_TOKENIZERS.register(LangId('zh'), morphman_jieba_tokenizer)

    # done
    return LOADED_USER_PROVIDED_TOKENIZERS
