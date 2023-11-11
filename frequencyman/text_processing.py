import re
import html
from typing import NewType, Optional

WordToken = NewType('WordToken', str)


class TextProcessing:

    @staticmethod
    def acceptable_word(word: str, lang_id: Optional[str] = None) -> bool:

        if (lang_id is not None and len(lang_id) != 2):
            raise ValueError(f"Invalid lang_id '{lang_id}'!")

        min_length = 1
        if lang_id in ['zh', 'ja']:
            word_pattern = re.compile(r'[\u4e00-\u9fff]{1,}', re.UNICODE)  # Chinese and Japanese characters
        elif lang_id in ['ko']:
            word_pattern = re.compile(r'[\uac00-\ud7a3]{1,}', re.UNICODE)  # Korean characters
        elif lang_id in ['ar']:
            word_pattern = re.compile(r'[\u0600-\u06FF]{1,}', re.UNICODE)  # Arabic characters
        elif lang_id in ['am', 'ti', 'om', 'so', 'ha']:
            word_pattern = re.compile(r'[\u1200-\u137F]{1,}', re.UNICODE)  # Ethiopic characters
        else:
            word_pattern = re.compile(r'[\w]{2,}', re.UNICODE)
            min_length = 2

        stripped_word = word.strip("!@#$%^&*()_-=+{}:\"<>?,./;' ")
        return len(stripped_word) >= min_length and len(stripped_word) < 300 and bool(re.search(word_pattern, stripped_word)) and not stripped_word.isdigit()

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
    def get_word_tokens_from_text(text: str, lang_id: Optional[str] = None) -> list[WordToken]:

        if (lang_id is not None and len(lang_id) != 2):
            raise ValueError(f"Invalid lang_id '{lang_id}'!")

        result_tokens = re.split(r"([^\w\-\_\'\’\.]{1,})", text)
        result_tokens = [s.strip(".'’") for s in result_tokens]
        word_tokens = [WordToken(token) for token in result_tokens if TextProcessing.acceptable_word(token, lang_id)]
        return word_tokens
