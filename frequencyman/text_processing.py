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
Tokenizer = Callable[[str], list[str]]

USER_PROVIDED_TOKENIZERS_LOADED: dict[LangId, Tokenizer] = {}

fm_plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
tokenizers_user_dir = os.path.join(fm_plugin_root, 'user_files', 'tokenizers')


# load custom defined tokenizers from user_files directory

if os.path.exists(tokenizers_user_dir):

    for sub_dir in os.listdir(tokenizers_user_dir):

        sub_dir_path = os.path.join(tokenizers_user_dir, sub_dir)
        init_module_name = 'fm_init_'+sub_dir
        fm_init_file = os.path.join(sub_dir_path, init_module_name+'.py')

        if not os.path.isdir(sub_dir_path):
            continue
        if not os.path.isfile(fm_init_file):
            continue

        sys.path.append(sub_dir_path)
        module = importlib.import_module(init_module_name, sub_dir_path)
        tokenizers_provider: Callable[[], list[tuple[str, Tokenizer]]] = getattr(module, sub_dir+'_tokenizers_provider')

        for lang_id, tokenizer in tokenizers_provider():
            if not isinstance(lang_id, str) or len(lang_id) != 2:
                raise Exception("Invalid lang_id given by provide_tokenizer in tokenizer {} in {}.".format(sub_dir, sub_dir_path))
            if LangId(lang_id) not in USER_PROVIDED_TOKENIZERS_LOADED:
                USER_PROVIDED_TOKENIZERS_LOADED[LangId(lang_id)] = tokenizer


#  mecab and jieba tokenizer from morphman plugin

morphman_plugin_path = os.path.abspath(os.path.join(fm_plugin_root, '..', '900801631'))
morphman_is_useful = not LangId('ja') in USER_PROVIDED_TOKENIZERS_LOADED or not LangId('zh') in USER_PROVIDED_TOKENIZERS_LOADED

if os.path.exists(morphman_plugin_path) and morphman_is_useful:

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
    def default_tokenizer(text: str) -> list[str]:

        return re.split(r"[^\w\-\_\'\’\.]{1,}", text)

    @staticmethod
    def get_tokenizer(lang_id: Optional[LangId] = None) -> Tokenizer:

        if not lang_id is None and lang_id in USER_PROVIDED_TOKENIZERS_LOADED:
            return USER_PROVIDED_TOKENIZERS_LOADED[lang_id]
        else:
            return TextProcessing.default_tokenizer

    @staticmethod
    def get_word_tokens_from_text(text: str, lang_id: Optional[LangId] = None) -> list[WordToken]:

        tokenizer = TextProcessing.get_tokenizer(lang_id)
        word_tokens = (TextProcessing.create_word_token(token, lang_id) for token in tokenizer(text))
        accepted_word_tokens = [token for token in word_tokens if TextProcessing.acceptable_word(token, lang_id)]
        return accepted_word_tokens
