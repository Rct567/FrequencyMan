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

    LANGUAGES_USING_APOSTROPHE = {
        'en',  # English (e.g., contractions like "don't")
        'fr',  # French (e.g., "l'heure")
        'it',  # Italian (e.g., "un'altra")
        'ga',  # Irish (Gaeilge, e.g., "O'Connell")
        'pt',  # Portuguese (e.g., poetic contractions)
        'de',  # German (e.g., genitive case in older texts)
        'nl',  # Dutch (e.g., shortened forms like "'s ochtends")
        'sv',  # Swedish (e.g., possessive forms like "Anna's")
        'fi',  # Finnish (e.g., loanwords like "taxi’t")
        'mt',  # Maltese (apostrophe in words like "qalb’i")
        'ca',  # Catalan (e.g., "l’àvia")
        'oc',  # Occitan (e.g., "l’aiga")
        'br',  # Breton
        'sw',  # Swahili (e.g., Ng'ombe)
        'tr',  # Turkish (e.g., İstanbul’a)
        'cy',  # Welsh (e.g., i’r)
        'gd',  # Scottish Gaelic (e.g., tha ’n)
        'gv',  # Manx (e.g., yn ’eddin)
        'mi',  # Māori (e.g., tā’onga)
        'nv',  # Navajo (e.g., łéʼéjí)
        'ku',  # Kurdish (e.g., k’u in Latin script)
        'az',  # Azerbaijani (e.g., Bakı’da)
        'uz',  # Uzbek (e.g., so’z)
        'ht',  # Haitian Creole (e.g., "pa'm" for "pou mwen")
        'nn',   # Norwegian Nynorsk (e.g., "kor'leis")
        'co',  # Corsican (e.g., "l'acqua")
        'gl',  # Galician (e.g., "n'a casa")
        'lb',  # Luxembourgish (e.g., "d'Stad")
        'qu',  # Quechua (e.g., "p'unchaw")
        'sc',  # Sardinian (e.g., "s'arti")
        'wa',   # Walloon (similar to French)
        'mg',  # Malagasy (e.g., "lao'ny")
        'rm',  # Romansh (e.g., "la 'n'oma")
    }

    CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]{1,}', re.UNICODE)
    JAPANESE_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf\uf900-\ufaff\u3400-\u4dbf]{1,}', re.UNICODE)
    KOREAN_PATTERN = re.compile(r'[\uac00-\ud7a3]{1,}', re.UNICODE)
    ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF]{1,}', re.UNICODE)
    ETHIOPIC_PATTERN = re.compile(r'[\u1200-\u137F]{1,}', re.UNICODE)
    THAI_PATTERN = re.compile(r'[\u0e00-\u0e7f]{1,}', re.UNICODE)
    LAO_PATTERN = re.compile(r'[\u0e80-\u0eff]{1,}', re.UNICODE)
    KHMER_PATTERN = re.compile(r'[\u1780-\u17ff]{1,}', re.UNICODE)
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
        elif lang_id is not None and str(lang_id) in {'am', 'ti'}:
            word_pattern = TextProcessing.ETHIOPIC_PATTERN
        elif lang_id == 'th':
            word_pattern = TextProcessing.THAI_PATTERN
        elif lang_id == 'lo':
            word_pattern = TextProcessing.LAO_PATTERN
        elif lang_id == 'km':
            word_pattern = TextProcessing.KHMER_PATTERN
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
    def get_word_token_creator(lang_id: LangId) -> Callable[[str], WordToken]:

        normalize_curly_apostrophe = str(lang_id) in TextProcessing.LANGUAGES_USING_APOSTROPHE

        def create_word_token(text: str) -> WordToken:

            assert "\t" not in text and "\n" not in text and "\r" not in text

            token = text.strip(".,'’\"' \t\n\r!@#$%^&*()_-=+{}:\"<>?/;")

            if normalize_curly_apostrophe and '’' in token:
                token = token.replace("’", "'")

            return WordToken(token.lower())

        return create_word_token

    @staticmethod
    def default_tokenizer(text: str) -> list[str]:

        text = str(text+" ").replace(". ", " ")
        non_word_chars = (
            r"[^\w\-\_\'\’\."
            r"\u0610-\u061A\u064B-\u065F" # Arabic diacritical marks
            r"\u0E00-\u0E7F"  # Thai script
            r"\u0E80-\u0EFF"  # Lao script
            r"\u1780-\u17FF"  # Khmer script
            r"]+"
        )
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
        create_word_token = TextProcessing.get_word_token_creator(lang_id)

        if tokenizer is None:
            tokenizer = TextProcessing.get_tokenizer(lang_id)
        else:  # tokenizer is provided, should only be used for testing
            user_provided_tokenizers = TextProcessing.get_user_provided_tokenizers()
            if not tokenizer in user_provided_tokenizers.get_all_tokenizers(lang_id):
                raise ValueError("Tokenizer '{}' is not a valid tokenizer for language {}!".format(tokenizer.__name__, lang_id))

        word_tokens = (create_word_token(token) for token in tokenizer(text))
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
