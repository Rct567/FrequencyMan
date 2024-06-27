"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import re
import html
from typing import Callable, NewType, Optional

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
    def get_word_accepter(lang_id: Optional[LangId]) -> Callable[[str], bool]:

        min_length = 1
        if lang_id == 'zh':
            word_pattern = TextProcessing.CHINESE_PATTERN
        elif lang_id == 'ja':
            word_pattern = TextProcessing.JAPANESE_PATTERN
        elif lang_id == 'ko':
            word_pattern = TextProcessing.KOREAN_PATTERN
        elif lang_id == 'ar':
            word_pattern = TextProcessing.ARABIC_PATTERN
        elif lang_id is not None and str(lang_id) in {'am', 'ti', 'om', 'so', 'ha'}:
            word_pattern = TextProcessing.ETHIOPIC_PATTERN
        else:
            word_pattern = TextProcessing.DEFAULT_PATTERN
            min_length = 2

        def is_acceptable_word_for_lang(word: str) -> bool:

            stripped_word = word.strip("!@#$%^&*()_-=+{}:\"<>?,./;' ")
            stripped_word_len = len(stripped_word)
            if stripped_word_len < min_length or stripped_word_len > 300:
                return False

            return re.search(word_pattern, stripped_word) is not None

        return is_acceptable_word_for_lang

    @staticmethod
    def get_plain_text(val: str) -> str:
        val = re.sub(r'<(style|head|script|object|noscript|embed|noembed|applet|canvas)(.*?)>(.*?)</\1>', ' ', val, flags=re.DOTALL)
        val = re.sub(r'</?(br|p|hr|div|pre|blockquote|h[1-6]|ul|ol|li|table|tr|td|th|dl|dd|dt)([^>]*)>', ' ', val, flags=re.IGNORECASE)
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

        text = str(text+" ").replace(". ", " ")
        # Arabic diacritical marks: u0610-\u061A\u064B-\u065F
        non_word_chars = r"[^\w\-\_\'\’\.\u0610-\u061A\u064B-\u065F]{1,}"
        return re.split(non_word_chars, text)

    @staticmethod
    def default_tokenizer_removing_possessives(text: str) -> list[str]:

        tokens = TextProcessing.default_tokenizer(text)

        for i, token in enumerate(tokens):
            if len(token) <= 3:
                continue
            if token[-1] == "s" and token[-2] in {"'", "’"}:
                tokens[i] = token[:-2]

        return tokens

    @staticmethod
    def get_user_provided_tokenizers() -> Tokenizers:

        if TextProcessing.user_provided_tokenizers is None:
            TextProcessing.user_provided_tokenizers = load_user_provided_tokenizers()

        return TextProcessing.user_provided_tokenizers

    @staticmethod
    def get_tokenizer(lang_id: LangId) -> Tokenizer:

        user_provided_tokenizers = TextProcessing.get_user_provided_tokenizers()

        if user_provided_tokenizers.lang_has_tokenizer(lang_id):
            return user_provided_tokenizers.get_tokenizer(lang_id)

        # or default tokenizer

        if lang_id in {LangId('en'), LangId('nl'), LangId('af')}:
            return TextProcessing.default_tokenizer_removing_possessives

        return TextProcessing.default_tokenizer

    @staticmethod
    def get_word_tokens_from_text(text: str, lang_id: LangId, tokenizer: Optional[Tokenizer] = None) -> list[WordToken]:

        is_acceptable_word = TextProcessing.get_word_accepter(lang_id)

        if tokenizer is None:
            tokenizer = TextProcessing.get_tokenizer(lang_id)
        else:  # tokenizer is provided, should only be used for testing
            user_provided_tokenizers = TextProcessing.get_user_provided_tokenizers()
            if not tokenizer in user_provided_tokenizers.get_all_tokenizers(lang_id):
                raise ValueError("Tokenizer '{}' is not a valid tokenizer for language {}!".format(tokenizer.__name__, lang_id))

        word_tokens = (TextProcessing.create_word_token(token, lang_id) for token in tokenizer(text))
        accepted_word_tokens = [token for token in word_tokens if is_acceptable_word(token)]
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
