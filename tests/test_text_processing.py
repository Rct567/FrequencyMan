import re
from frequencyman.text_processing import LangId, TextProcessing


def test_acceptable_word():

    assert TextProcessing.acceptable_word("app-le") == True
    assert TextProcessing.acceptable_word("won't") == True
    assert TextProcessing.acceptable_word("你", LangId("zh")) == True

    assert TextProcessing.acceptable_word("s") == False
    assert TextProcessing.acceptable_word("s ") == False
    assert TextProcessing.acceptable_word("s!!!") == False
    assert TextProcessing.acceptable_word("_s_") == False
    assert TextProcessing.acceptable_word("1234") == False
    assert TextProcessing.acceptable_word("$$$$$$$") == False


def test_get_plain_text():

    assert TextProcessing.get_plain_text("This a <b>sample</b></b> text with HTML<p>tags</P>and example.") == "This a sample text with HTML tags and example."
    assert TextProcessing.get_plain_text("This a <script> kk </script> example.") == "This a example."
    assert TextProcessing.get_plain_text("This N&amp;M that") == "This N&M that"
    assert TextProcessing.get_plain_text("Non-breaking space: This&nbsp;is&nbsp;a&nbsp;test.") == "Non-breaking space: This is a test."
    assert TextProcessing.get_plain_text("This [sound:azure-57d4ff9d-b02968eb-9f293f42-b1c6426f-2dd6b8a7.mp3]") == "This"
    assert TextProcessing.get_plain_text("Use of [brackets] <b>[inside HTML]</b> tags.") == "Use of [brackets] [inside HTML] tags."


def test_get_word_tokens_from_text():

    text_with_special_chars = "I can't \"believe\" it's here (wow) 1-character! 'amazinG'"
    assert TextProcessing.get_word_tokens_from_text(text_with_special_chars) == ["can't", "believe", "it's", "here", "wow", "1-character", "amazing"]

    # Test with an empty string
    assert TextProcessing.get_word_tokens_from_text("") == []
    assert TextProcessing.get_word_tokens_from_text("12345") == []

    assert TextProcessing.get_word_tokens_from_text("Simple sente-nce. EE.UU.") == ['simple', 'sente-nce', 'ee.uu']
    assert TextProcessing.get_word_tokens_from_text("This is a\ttest.\t") == ['this', 'is', 'test']
    assert TextProcessing.get_word_tokens_from_text("Hello, world!") == ['hello', 'world']

    assert TextProcessing.get_word_tokens_from_text("Мне … лет.") == ['мне', 'лет']
    assert TextProcessing.get_word_tokens_from_text("你跟我") == ['你跟我']


def test_get_word_token():

    assert TextProcessing.create_word_token("$$hellO") == "hello"
    assert TextProcessing.create_word_token("Iñtërnâtiônàlizætiøn") == "iñtërnâtiônàlizætiøn"
