import re
from frequencyman.text_processing import USER_PROVIDED_TOKENIZERS_LOADED, LangId, TextProcessing


def test_acceptable_word():

    assert TextProcessing.acceptable_word("app-le") == True
    assert TextProcessing.acceptable_word("app---le") == True
    assert TextProcessing.acceptable_word("won't") == True
    assert TextProcessing.acceptable_word("iñtërnâtiônàlizætiøn") == True
    assert TextProcessing.acceptable_word("你", LangId("zh")) == True

    assert TextProcessing.acceptable_word("s") == False
    assert TextProcessing.acceptable_word("s ") == False
    assert TextProcessing.acceptable_word("s!!!") == False
    assert TextProcessing.acceptable_word("_s_") == False
    assert TextProcessing.acceptable_word("1234") == False
    assert TextProcessing.acceptable_word("1.123") == False
    assert TextProcessing.acceptable_word("$$$$$$$") == False
    assert TextProcessing.acceptable_word("___") == False


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


def test_get_word_tokens_from_text_user_tokenizer_ja():

    if not LangId('ja') in USER_PROVIDED_TOKENIZERS_LOADED:
        print("User tokenizer for JA test skipped!!!")
        return
    else:
        print("User tokenizer for JA tested: "+USER_PROVIDED_TOKENIZERS_LOADED[LangId('ja')].__name__)

    assert TextProcessing.get_word_tokens_from_text("すもももももももものうち", LangId('ja')) == ['すもも', 'も', 'もも', 'も', 'もも', 'の', 'うち']
    assert TextProcessing.get_word_tokens_from_text("こんにちは。私の名前はシャンです。", LangId('ja')) == ["こんにちは", "私", "の", "名前", "は", "シャン", "です"]


def test_get_word_tokens_from_text_user_tokenizer_zh():

    if not LangId('zh') in USER_PROVIDED_TOKENIZERS_LOADED:
        print("User tokenizer for ZH test skipped!!!")
        return
    else:
        print("User tokenizer for ZH tested: "+USER_PROVIDED_TOKENIZERS_LOADED[LangId('zh')].__name__)

    assert TextProcessing.get_word_tokens_from_text("你跟我", LangId('zh')) == ['你', '跟', '我']
    assert TextProcessing.get_word_tokens_from_text("hello 吃饭了吗😊? ", LangId('zh')) == ["吃饭", "了", "吗"]
    assert TextProcessing.get_word_tokens_from_text("我爱自然语言处理。", LangId('zh')) == ['我', '爱', '自然语言', '处理']


def test_create_word_token():

    assert TextProcessing.create_word_token("$$hellO") == "hello"
    assert TextProcessing.create_word_token("hello!") == "hello"
    assert TextProcessing.create_word_token("Iñtërnâtiônàlizætiøn") == "iñtërnâtiônàlizætiøn"


def test_calc_word_presence_score():

    token_context = TextProcessing.get_word_tokens_from_text("test")
    assert TextProcessing.calc_word_presence_score(token_context[0], token_context, 0) == 1.0

    token_context = TextProcessing.get_word_tokens_from_text("test abcd")
    assert TextProcessing.calc_word_presence_score(token_context[0], token_context, 0) == (0.5+0.5+1)/3

    token_context = TextProcessing.get_word_tokens_from_text("test abcdabcd")
    assert TextProcessing.calc_word_presence_score(token_context[0], token_context, 0) == (0.5+(1/3)+1)/3

    token_context = TextProcessing.get_word_tokens_from_text("test test abcd")
    assert TextProcessing.calc_word_presence_score(token_context[0], token_context, 1) == ((2/3)+(2/3)+0.5)/3
