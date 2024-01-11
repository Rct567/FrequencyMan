"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import importlib
import os
import re
import html
import sys
from typing import Any, Callable, NewType, Optional
from typing import TYPE_CHECKING

from .lib.utilities import var_dump, var_dump_log

WordToken = NewType('WordToken', str)
LangId = NewType('LangId', str)

USER_PROVIDED_TOKENIZERS_LOADED: dict[LangId, Callable[[str], list[str]]] = {}

fm_plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
tokenizers_user_dir = os.path.join(fm_plugin_root, 'user_files', 'tokenizers')

if os.path.exists(tokenizers_user_dir):

    sys.path.append(tokenizers_user_dir)

    # jieba tokenizer (zh) from user_files/tokenizers

    if os.path.exists(os.path.join(tokenizers_user_dir, 'jieba')) and not LangId('zh') in USER_PROVIDED_TOKENIZERS_LOADED:

        if TYPE_CHECKING:
            from ..user_files.tokenizers.jieba import lcut as jieba_lcut, setLogLevel as jieba_set_log_level
        else:
            from jieba import lcut as jieba_lcut, setLogLevel as jieba_set_log_level

        jieba_set_log_level('WARNING')

        def jieba_tokenizer_user_files(txt: str) -> list[str]:
            return list(token for token in jieba_lcut(txt) if token is not None)

        USER_PROVIDED_TOKENIZERS_LOADED[LangId('zh')] = jieba_tokenizer_user_files

    # janome tokenizer (ja) from user_files/tokenizers

    if os.path.exists(os.path.join(tokenizers_user_dir, 'janome')) and not LangId('ja') in USER_PROVIDED_TOKENIZERS_LOADED:

        if TYPE_CHECKING:
            from ..user_files.tokenizers.janome.tokenizer import Tokenizer
        else:
            from janome.tokenizer import Tokenizer
        JANOME_TOKENIZER = Tokenizer()

        def janome_tokenizer_user_files(txt: str) -> list[str]:
            result_list = list(token for token in JANOME_TOKENIZER.tokenize(txt, wakati=True) if isinstance(token, str))
            return result_list

        USER_PROVIDED_TOKENIZERS_LOADED[LangId('ja')] = janome_tokenizer_user_files

#  morphman mecab and jieba

morphman_plugin_path = os.path.abspath(os.path.join(fm_plugin_root, '..', '900801631'))

if os.path.exists(morphman_plugin_path):

    sys.path.append(morphman_plugin_path)
    morphemizer_module = importlib.import_module('morph.morphemizer')

    if not LangId('ja') in USER_PROVIDED_TOKENIZERS_LOADED:

        morphemizer_mecab = morphemizer_module.getMorphemizerByName("MecabMorphemizer")

        def morphman_mecab_tokenizer(txt: str) -> list[str]:
            return [token.base for token in morphemizer_mecab.getMorphemesFromExpr(txt)]

        USER_PROVIDED_TOKENIZERS_LOADED[LangId('ja')] = morphman_mecab_tokenizer

    if not LangId('zh') in USER_PROVIDED_TOKENIZERS_LOADED:

        morphemizer_jieba = morphemizer_module.getMorphemizerByName("JiebaMorphemizer")

        def morphman_jieba_tokenizer(txt: str) -> list[str]:
            return [token.base for token in morphemizer_jieba.getMorphemesFromExpr(txt)]

        USER_PROVIDED_TOKENIZERS_LOADED[LangId('zh')] = morphman_jieba_tokenizer



# text processing class

class TextProcessing:

    CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]{1,}', re.UNICODE)
    JAPANESE_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf\uf900-\ufaff\u3400-\u4dbf]{1,}', re.UNICODE)
    KOREAN_PATTERN = re.compile(r'[\uac00-\ud7a3]{1,}', re.UNICODE)
    ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF]{1,}', re.UNICODE)
    ETHIOPIC_PATTERN = re.compile(r'[\u1200-\u137F]{1,}', re.UNICODE)
    DEFAULT_PATTERN = re.compile(r'[\w]{2,}', re.UNICODE)

    @staticmethod
    def acceptable_word(word: str, lang_id: Optional[LangId] = None) -> bool:

        min_length = 1
        if lang_id == 'zh':
            word_pattern = TextProcessing.CHINESE_PATTERN
        elif lang_id == 'ja':
            word_pattern = TextProcessing.JAPANESE_PATTERN
        elif lang_id == 'ko':
            word_pattern = TextProcessing.KOREAN_PATTERN
        elif lang_id == 'ar':
            word_pattern = TextProcessing.ARABIC_PATTERN
        elif lang_id in {'am', 'ti', 'om', 'so', 'ha'}:
            word_pattern = TextProcessing.ETHIOPIC_PATTERN
        else:
            word_pattern = TextProcessing.DEFAULT_PATTERN
            min_length = 2

        stripped_word = word.strip("!@#$%^&*()_-=+{}:\"<>?,./;' ")
        stripped_word_len = len(stripped_word)
        if stripped_word_len < min_length or stripped_word_len > 300:
            return False

        return bool(re.search(word_pattern, stripped_word)) and not stripped_word.isdigit()

    @staticmethod
    def get_plain_text(val: str) -> str:
        val = re.sub(r'<(style|head|script|object|noscript|embed|noembed|applet)(.*?)>(.*?)</\1>', ' ', val, flags=re.DOTALL)
        val = re.sub(r'</?(p|div|blockquote|h[1-6]|ul|ol|li|table|tr|td|th)([^>]*)>', ' ', val, flags=re.IGNORECASE)
        val = re.sub(r'<[^>]+>', '', val)
        val = re.sub(r"\[(sound|type):[^]]+\]", " ", val)
        val = html.unescape(val)
        val = re.sub(r'[\s]+', ' ', val)
        return val.strip()

    @staticmethod
    def create_word_token(text: str, lang_id: Optional[LangId] = None) -> WordToken:

        assert "\t" not in text and "\n" not in text and "\r" not in text

        token = text.strip(".,'’\"' \t\n\r!@#$%^&*()_-=+{}:\"<>?/;")
        return WordToken(token.lower())

    @staticmethod
    def tokenize_text(text: str, lang_id: Optional[LangId] = None) -> list[str]:

        if not lang_id is None and lang_id in USER_PROVIDED_TOKENIZERS_LOADED:
            result_tokens = USER_PROVIDED_TOKENIZERS_LOADED[lang_id](text)
        else:
            result_tokens = re.split(r"[^\w\-\_\'\’\.]{1,}", text)

        return result_tokens

    @staticmethod
    def get_word_tokens_from_text(text: str, lang_id: Optional[LangId] = None) -> list[WordToken]:

        text_tokens = TextProcessing.tokenize_text(text, lang_id)

        result_tokens = [TextProcessing.create_word_token(token, lang_id) for token in text_tokens]
        word_tokens = [token for token in result_tokens if TextProcessing.acceptable_word(token, lang_id)]
        return word_tokens
