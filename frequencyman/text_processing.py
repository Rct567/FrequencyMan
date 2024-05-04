"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import os
import re
import html
from typing import NewType, Optional

from .tokenizers import Tokenizers, load_user_provided_tokenizers, Tokenizer, LangId


WordToken = NewType('WordToken', str)

class TextProcessing:

    CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]{1,}', re.UNICODE)
    JAPANESE_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf\uf900-\ufaff\u3400-\u4dbf]{1,}', re.UNICODE)
    KOREAN_PATTERN = re.compile(r'[\uac00-\ud7a3]{1,}', re.UNICODE)
    ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF]{1,}', re.UNICODE)
    ETHIOPIC_PATTERN = re.compile(r'[\u1200-\u137F]{1,}', re.UNICODE)
    DEFAULT_PATTERN = re.compile(r'[^\W\d_]{2,}', re.UNICODE)

    user_provided_tokenizers: Optional[Tokenizers] = None

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

        return re.search(word_pattern, stripped_word) is not None

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
    def get_user_provided_tokenizers() -> Tokenizers:

        if TextProcessing.user_provided_tokenizers is None:
            TextProcessing.user_provided_tokenizers = load_user_provided_tokenizers()

        return TextProcessing.user_provided_tokenizers

    @staticmethod
    def get_tokenizer(lang_id: Optional[LangId] = None) -> Tokenizer:

        user_provided_tokenizers = TextProcessing.get_user_provided_tokenizers()

        if not lang_id is None and user_provided_tokenizers.lang_has_tokenizer(lang_id):
            return user_provided_tokenizers.get_tokenizer(lang_id)

        return TextProcessing.default_tokenizer

    @staticmethod
    def get_word_tokens_from_text(text: str, lang_id: Optional[LangId] = None, tokenizer: Optional[Tokenizer] = None) -> list[WordToken]:

        if tokenizer is None:
            tokenizer = TextProcessing.get_tokenizer(lang_id)
        elif lang_id is None:
            raise ValueError("Lang_id required when tokenizer is provided!")
        else:  # tokenizer is provided, should only be used for testing
            user_provided_tokenizers = TextProcessing.get_user_provided_tokenizers()
            if not tokenizer in user_provided_tokenizers.get_all_tokenizers(lang_id):
                raise ValueError("Tokenizer '{}' is not a valid tokenizer for language {}!".format(tokenizer.__name__, lang_id))

        word_tokens = (TextProcessing.create_word_token(token, lang_id) for token in tokenizer(text))
        accepted_word_tokens = [token for token in word_tokens if TextProcessing.acceptable_word(token, lang_id)]
        return accepted_word_tokens

    @staticmethod
    def calc_word_presence_score(word: WordToken, context: list[WordToken], position_index: int) -> float:

        assert word in context
        assert word == context[position_index]

        word_count = context.count(word)
        context_num_words = len(context)
        context_num_chars = len(''.join(context))

        presence_score_by_words = word_count/context_num_words
        presence_score_by_chars = (len(word)*word_count)/context_num_chars
        position_value = 1/(position_index+1)

        return (presence_score_by_words+presence_score_by_chars+position_value)/3
