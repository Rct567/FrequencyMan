"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from abc import ABC, abstractmethod
from collections import UserString
from functools import cache
import importlib
import os
import re
import sys
from types import ModuleType
from typing import Callable, Optional, Sequence


from .lib.utilities import override


class LangId(UserString):

    def __init__(self, lang_id: str) -> None:
        assert len(lang_id) == 2, "Two characters only for LangId!"
        assert lang_id.isalpha(), "Only alphabetic characters for LangId!"
        assert lang_id.islower(), "Lowercase only for LangId!"
        super().__init__(lang_id)


CallableTokenizerFn = Callable[[str], Sequence[str]]


class Tokenizer(ABC):

    _initialized: bool = False

    def name(self) -> str:
        if hasattr(self, '_tokenizer_id'):
            return self.__class__.__name__+'('+self._tokenizer_id+')'  # type: ignore

        return self.__class__.__name__

    @abstractmethod
    def tokenize(self, text: str) -> Sequence[str]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def supported_languages(self) -> set[LangId]:
        pass

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self._initialize()
            self._initialized = True

    def _initialize(self) -> None:
        pass


WHITE_SPACE_LANGUAGES = {
    'aa', 'ab', 'af', 'ak', 'am', 'an', 'ar', 'as', 'av', 'ay', 'az', 'ba', 'be',
    'bg', 'bh', 'bi', 'bm', 'bn', 'br', 'bs', 'ca', 'ce', 'ch', 'co', 'cr', 'cs',
    'cu', 'cv', 'cy', 'da', 'de', 'dv', 'ee', 'el', 'en', 'eo', 'es', 'et', 'eu',
    'fa', 'ff', 'fi', 'fj', 'fo', 'fr', 'fy', 'ga', 'gd', 'gl', 'gn', 'gu', 'gv',
    'ha', 'he', 'hi', 'ho', 'hr', 'ht', 'hu', 'hy', 'hz', 'ia', 'id', 'ie', 'ig',
    'ik', 'io', 'is', 'it', 'iu', 'jv', 'ka', 'kg', 'ki', 'kj', 'kk', 'kl', 'kn',
    'ko', 'kr', 'ks', 'ku', 'kv', 'kw', 'ky', 'la', 'lb', 'lg', 'li', 'ln', 'lt',
    'lu', 'lv', 'mg', 'mh', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'na', 'nb',
    'nd', 'ne', 'ng', 'nl', 'nn', 'no', 'nr', 'nv', 'ny', 'oc', 'oj', 'om', 'or',
    'os', 'pa', 'pi', 'pl', 'ps', 'pt', 'qu', 'rm', 'rn', 'ro', 'ru', 'rw', 'sa',
    'sc', 'sd', 'se', 'sg', 'si', 'sk', 'sl', 'sm', 'sn', 'so', 'sq', 'sr', 'ss',
    'st', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'ti', 'tk', 'tl', 'tn', 'to', 'tr',
    'ts', 'tt', 'tw', 'ty', 'ug', 'uk', 'ur', 'uz', 've', 'vi', 'vo', 'wa', 'wo',
    'xh', 'yi', 'yo', 'za', 'zu'
}


class DefaultTokenizer(Tokenizer):

    @override
    def is_available(self) -> bool:
        return True

    @override
    def supported_languages(self) -> set[LangId]:
        return {LangId(lang_id) for lang_id in WHITE_SPACE_LANGUAGES}

    @override
    def tokenize(self, text: str) -> Sequence[str]:

        text = str(text+" ").replace(". ", " ")
        non_word_chars = (
            r"[^\w\-\_\'\’\."
            r"\u0610-\u061A\u064B-\u065F"  # Arabic diacritical marks
            r"\u0E00-\u0E7F"  # Thai script
            r"\u0E80-\u0EFF"  # Lao script
            r"\u1780-\u17FF"  # Khmer script
            r"]+"
        )
        return re.split(non_word_chars, text)


class DefaultTokenizerRemovingPossessives(DefaultTokenizer):

    @override
    def supported_languages(self) -> set[LangId]:
        return {LangId('en'), LangId('nl'), LangId('af')}

    @override
    def tokenize(self, text: str) -> Sequence[str]:

        tokens = list(DefaultTokenizer().tokenize(text))

        for i, token in enumerate(tokens):
            if len(token) <= 3:
                continue
            if token[-1] == "s" and token[-2] in {"'", "’"}:
                tokens[i] = token[:-2]

        return tokens


class UserProvidedTokenizer(Tokenizer):
    """Tokenizer loaded from user_files directory."""

    def __init__(self, tokenizer_dir: str, tokenizer_id: str, lang_id: str) -> None:
        self._tokenizer_dir = tokenizer_dir
        self._tokenizer_id = tokenizer_id
        self._lang_id = LangId(lang_id)
        self._tokenize_func: Optional[CallableTokenizerFn] = None

    @override
    def is_available(self) -> bool:
        tokenizer_init_module_name = f'fm_init_{self._tokenizer_id}'
        module_path = os.path.join(self._tokenizer_dir, f'{tokenizer_init_module_name}.py')
        subdir_path = os.path.join(self._tokenizer_dir, self._tokenizer_id)
        return os.path.exists(module_path) and os.path.isdir(subdir_path)

    @override
    def supported_languages(self) -> set[LangId]:
        return {self._lang_id}

    @override
    def _initialize(self) -> None:
        tokenizer_init_module_name = f'fm_init_{self._tokenizer_id}'
        sys.path.append(self._tokenizer_dir)
        module = importlib.import_module(tokenizer_init_module_name, self._tokenizer_dir)
        tokenizers_provider = getattr(module, f'{self._tokenizer_id}_tokenizers_provider')

        # Find the tokenizer function for our language
        for lang_id, tokenizer_func in tokenizers_provider():
            if lang_id == self._lang_id.data:
                self._tokenize_func = tokenizer_func
                break

    @override
    def tokenize(self, text: str) -> Sequence[str]:
        self._ensure_initialized()
        if self._tokenize_func is None:
            raise RuntimeError(f"Tokenizer for {self._tokenizer_id} not properly initialized")
        return self._tokenize_func(text)


class AnkiMorphsJiebaTokenizer(Tokenizer):
    """Jieba tokenizer from ankimorphs-chinese-jieba plugin."""

    def __init__(self, anki_plugins_dir: str) -> None:
        self._anki_plugins_dir = anki_plugins_dir
        self._plugin_path = os.path.join(anki_plugins_dir, '1857311956')
        self._jieba_module: Optional[ModuleType] = None

    @override
    def is_available(self) -> bool:
        return os.path.exists(self._plugin_path)

    @override
    def supported_languages(self) -> set[LangId]:
        return {LangId('zh')}

    @override
    def _initialize(self) -> None:
        sys.path.append(self._anki_plugins_dir)
        self._jieba_module = importlib.import_module("1857311956.jieba.posseg")

    @override
    def tokenize(self, text: str) -> list[str]:
        self._ensure_initialized()
        if self._jieba_module is None:
            raise RuntimeError("Jieba module not loaded")
        return [token for (token, _) in self._jieba_module.lcut(text) if token is not None]


class AnkiMorphsMecabTokenizer(Tokenizer):
    """MeCab tokenizer from ankimorphs-japanese-mecab plugin."""

    def __init__(self, anki_plugins_dir: str) -> None:
        self._anki_plugins_dir = anki_plugins_dir
        self._plugin_path = os.path.join(anki_plugins_dir, '1974309724')
        self._mecab_module: Optional[ModuleType] = None
        self._get_morphemes_func: Optional[CallableTokenizerFn] = None

    @override
    def is_available(self) -> bool:
        return os.path.exists(self._plugin_path)

    @override
    def supported_languages(self) -> set[LangId]:
        return {LangId('ja')}

    @override
    def _initialize(self) -> None:
        sys.path.append(self._anki_plugins_dir)
        self._mecab_module = importlib.import_module("1974309724.reading")

        from .anki_morphs_mecab_wrapper import setup_mecab, get_morphemes_mecab
        setup_mecab(self._mecab_module)
        self._get_morphemes_func = get_morphemes_mecab

    @override
    def tokenize(self, text: str) -> Sequence[str]:
        self._ensure_initialized()
        if self._get_morphemes_func is None:
            raise RuntimeError("MeCab morphemes function not loaded")
        return self._get_morphemes_func(text)


class AjtJapaneseMecabTokenizer(Tokenizer):
    """MeCab tokenizer from 'ajt japanese' plugin."""

    def __init__(self, anki_plugins_dir: str) -> None:
        self._anki_plugins_dir = anki_plugins_dir
        self._plugin_path = os.path.join(anki_plugins_dir, '1344485230')
        self._mecab: Optional[ModuleType] = None

    @override
    def is_available(self) -> bool:
        return os.path.exists(self._plugin_path)

    @override
    def supported_languages(self) -> set[LangId]:
        return {LangId('ja')}

    @override
    def _initialize(self) -> None:
        sys.path.append(self._plugin_path)
        ajt_japanese_module = importlib.import_module('mecab_controller.mecab_controller')
        self._mecab = ajt_japanese_module.MecabController(verbose=False)

    @override
    def tokenize(self, text: str) -> list[str]:
        self._ensure_initialized()
        if self._mecab is None:
            raise RuntimeError("AJT MeCab not loaded")
        return [token.word for token in self._mecab.translate(text)]


class MorphmanMecabTokenizer(Tokenizer):
    """MeCab tokenizer from 'morphman' plugin."""

    def __init__(self, anki_plugins_dir: str) -> None:
        self._anki_plugins_dir = anki_plugins_dir
        self._plugin_path = os.path.join(anki_plugins_dir, '900801631')
        self._morphemizer: Optional[ModuleType] = None

    @override
    def is_available(self) -> bool:
        return os.path.exists(self._plugin_path)

    @override
    def supported_languages(self) -> set[LangId]:
        return {LangId('ja')}

    @override
    def _initialize(self) -> None:
        sys.path.append(self._plugin_path)
        morphemizer_module = importlib.import_module('morph.morphemizer')
        self._morphemizer = morphemizer_module.getMorphemizerByName("MecabMorphemizer")

    @override
    def tokenize(self, text: str) -> list[str]:
        self._ensure_initialized()
        if self._morphemizer is None:
            raise RuntimeError("Morphman MeCab not loaded")
        return [token.base for token in self._morphemizer.getMorphemesFromExpr(text)]


class MorphmanJiebaTokenizer(Tokenizer):
    """Jieba tokenizer from 'morphman' plugin."""

    def __init__(self, anki_plugins_dir: str) -> None:
        self._anki_plugins_dir = anki_plugins_dir
        self._plugin_path = os.path.join(anki_plugins_dir, '900801631')
        self._morphemizer: Optional[ModuleType] = None

    @override
    def is_available(self) -> bool:
        return os.path.exists(self._plugin_path)

    @override
    def supported_languages(self) -> set[LangId]:
        return {LangId('zh')}

    @override
    def _initialize(self) -> None:
        sys.path.append(self._plugin_path)
        morphemizer_module = importlib.import_module('morph.morphemizer')
        self._morphemizer = morphemizer_module.getMorphemizerByName("JiebaMorphemizer")

    @override
    def tokenize(self, text: str) -> list[str]:
        self._ensure_initialized()
        if self._morphemizer is None:
            raise RuntimeError("Morphman Jieba not loaded")
        return [token.base for token in self._morphemizer.getMorphemesFromExpr(text)]


# Global registry of tokenizers (loaded only once)
_tokenizer_registry: Optional[list[Tokenizer]] = None


def get_tokenizer_registry() -> list[Tokenizer]:
    """Get or create the global tokenizer registry."""
    global _tokenizer_registry

    if _tokenizer_registry is not None:
        return _tokenizer_registry

    fm_plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    anki_plugins_dir = os.path.abspath(os.path.join(fm_plugin_root, '..'))
    tokenizers_user_dir = os.path.join(fm_plugin_root, 'user_files', 'tokenizers')

    if not os.path.exists(anki_plugins_dir):
        raise Exception("Could not find anki plugin directory!")

    _tokenizer_registry = []

    # Load custom defined tokenizers from user_files directory
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

            # Load the module temporarily to get language information
            tokenizer_init_module_name = 'fm_init_'+tokenizer_id
            sys.path.append(tokenizer_dir)
            module = importlib.import_module(tokenizer_init_module_name, tokenizer_dir)
            tokenizers_provider = getattr(module, tokenizer_id+'_tokenizers_provider')

            for lang_id, _ in tokenizers_provider():
                if not isinstance(lang_id, str) or len(lang_id) != 2:
                    raise Exception("Invalid lang_id given by '{}' in '{}'.".format(tokenizers_provider.__name__, tokenizer_dir))

                _tokenizer_registry.append(
                    UserProvidedTokenizer(tokenizer_dir, tokenizer_id, lang_id)
                )

    # Add all plugin-based tokenizers
    _tokenizer_registry.extend([
        AnkiMorphsJiebaTokenizer(anki_plugins_dir),
        AnkiMorphsMecabTokenizer(anki_plugins_dir),
        AjtJapaneseMecabTokenizer(anki_plugins_dir),
        MorphmanMecabTokenizer(anki_plugins_dir),
        MorphmanJiebaTokenizer(anki_plugins_dir),
        DefaultTokenizerRemovingPossessives(),
        DefaultTokenizer(),
    ])

    return _tokenizer_registry


@cache
def get_user_provided_tokenizer(lang_id: LangId) -> Tokenizer:

    tokenizers = get_tokenizer_registry()

    for tokenizer in tokenizers:
        if not tokenizer.is_available():
            continue
        if lang_id in tokenizer.supported_languages():
            return tokenizer

    return DefaultTokenizer()
