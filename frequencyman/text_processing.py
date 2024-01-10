"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import re
import html
from typing import NewType, Optional

WordToken = NewType('WordToken', str)
LangId = NewType('LangId', str)


class TextProcessing:

    CHINESE_JAPANESE_PATTERN = re.compile(r'[\u4e00-\u9fff]{1,}', re.UNICODE)
    KOREAN_PATTERN = re.compile(r'[\uac00-\ud7a3]{1,}', re.UNICODE)
    ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF]{1,}', re.UNICODE)
    ETHIOPIC_PATTERN = re.compile(r'[\u1200-\u137F]{1,}', re.UNICODE)
    DEFAULT_PATTERN = re.compile(r'[\w]{2,}', re.UNICODE)

    @staticmethod
    def acceptable_word(word: str, lang_id: Optional[LangId] = None) -> bool:

        min_length = 1
        if lang_id == 'zh':
            word_pattern = TextProcessing.CHINESE_JAPANESE_PATTERN
        elif lang_id == 'ja':
            word_pattern = TextProcessing.CHINESE_JAPANESE_PATTERN
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
    def get_word_tokens_from_text(text: str, lang_id: Optional[LangId] = None) -> list[WordToken]:
        result_tokens = re.split(r"[^\w\-\_\'\’\.]{1,}", text)
        result_tokens = [TextProcessing.create_word_token(token, lang_id) for token in result_tokens]
        word_tokens = [token for token in result_tokens if TextProcessing.acceptable_word(token, lang_id)]
        return word_tokens
