import re

class TextProcessing:
    
    @staticmethod
    def acceptable_word(word:str) -> bool:
        word_pattern = re.compile(r'\w{2,}', re.UNICODE)
        acceptable = len(word) < 300 and len(word) > 1 and bool(re.search(word_pattern, word))
        return acceptable;

    @staticmethod
    def get_plain_text(val:str) -> str:
        #val = re.sub(r'<(p|div|blockquote|h1|h2|h3|h4|h5|h6|ul|ol|li|table|tr|td|th)(.*?)>(.*?)</\1>', ' ', val, flags=re.DOTALL)
        val = re.sub(r'</?(p|div|blockquote|h[1-6]|ul|ol|li|table|tr|td|th)([^>]*)>', ' ', val, flags=re.IGNORECASE)
        val = re.sub(r'<[^>]+>', '', val)
        val = re.sub(r"\[sound:[^]]+\]", " ", val)
        val = re.sub(r"\[\[type:[^]]+\]\]", " ", val)
        return val
    
    @staticmethod
    def get_word_tokens_from_text(text: str) -> list:
        # Use a regular expression to find word tokens
        word_tokens = re.split(r'[\s?!,\(\)\{\}]+', text)
        word_tokens = [token for token in word_tokens if TextProcessing.acceptable_word(token)]
        return word_tokens