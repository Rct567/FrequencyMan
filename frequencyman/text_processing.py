"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import Counter
import re
import html
from typing import Callable, NewType, Optional
from collections.abc import Sequence

from .tokenizers import get_user_provided_tokenizer, Tokenizer, LangId


WordToken = NewType('WordToken', str)


class TextProcessing:

    LANGUAGES_USING_APOSTROPHE = {
        'en',  # English (e.g., contractions like "don't")
        'fr',  # French (e.g., "l'heure")
        'it',  # Italian (e.g., "un'altra")
        'ga',  # Irish (Gaeilge, e.g., "O'Connell")
        'pt',  # Portuguese (e.g., poetic contractions)
        'pt_br',  # Portuguese (Brazil)
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
        'nn',  # Norwegian Nynorsk (e.g., "kor'leis")
        'nb',  # Norwegian Bokmål (e.g., "kor'leis")
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
        elif lang_id is not None and lang_id in {'am', 'ti'}:
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

        normalize_curly_apostrophe = lang_id in TextProcessing.LANGUAGES_USING_APOSTROPHE

        def create_word_token(text: str) -> WordToken:

            assert "\t" not in text and "\n" not in text and "\r" not in text

            token = text.strip(".,'’\" \t\n\r!@#$%^&*()_-=+{}:<>?/;")

            if normalize_curly_apostrophe and '’' in token:
                token = token.replace("’", "'")

            return WordToken(token.lower())

        return create_word_token

    @staticmethod
    def get_word_tokens_from_text(text: str, lang_id: LangId, tokenizer: Optional[Tokenizer] = None) -> Sequence[WordToken]:

        is_acceptable_word = TextProcessing.get_word_accepter(lang_id)
        create_word_token = TextProcessing.get_word_token_creator(lang_id)

        if tokenizer is None:
            tokenizer = get_user_provided_tokenizer(lang_id)
        else:  # tokenizer is provided, should only be used for testing
            if not lang_id in tokenizer.supported_languages():
                raise ValueError("Provided tokenizer '{}' does not support '{}'.".format(tokenizer.__class__.__name__, lang_id))

        word_tokens = (create_word_token(token) for token in tokenizer.tokenize(text))
        accepted_word_tokens = [token for token in word_tokens if is_acceptable_word(token)]
        return accepted_word_tokens

    @staticmethod
    def calc_word_presence_scores(context: Sequence[WordToken]) -> list[tuple[WordToken, float]]:
        context_num_words = len(context)

        if context_num_words == 0:
            return []
        if context_num_words == 1:
            return [(context[0], 1.0)]

        counts: dict[WordToken, int] = {}
        word_lengths: dict[WordToken, int] = {}
        context_num_chars = 0

        for word in context:
            if word in counts:
                counts[word] += 1
                context_num_chars += word_lengths[word]
            else:
                counts[word] = 1
                word_len = len(word)
                word_lengths[word] = word_len
                context_num_chars += word_len

        inv_num_words = 1.0 / context_num_words
        inv_num_chars = 1.0 / context_num_chars
        inv_three = 1.0 / 3.0

        results: list[tuple[WordToken, float]] = []

        for position_index in range(context_num_words):
            word = context[position_index]
            word_count = counts[word]
            word_len = word_lengths[word]

            results.append((
                word,
                (word_count * inv_num_words +
                 (word_len * word_count) * inv_num_chars +
                 1.0 / (position_index + 1)) * inv_three
            ))

        return results
