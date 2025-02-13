from frequencyman.text_processing import LangId, TextProcessing

USER_PROVIDED_TOKENIZERS = TextProcessing.get_user_provided_tokenizers()


def test_acceptable_word():

    is_acceptable_word = TextProcessing.get_word_accepter(None)
    is_acceptable_word_zh = TextProcessing.get_word_accepter(LangId("zh"))
    is_acceptable_word_vi = TextProcessing.get_word_accepter(LangId("vi"))

    assert is_acceptable_word("app-le") == True
    assert is_acceptable_word("app---le") == True
    assert is_acceptable_word("won't") == True
    assert is_acceptable_word("iñtërnâtiônàlizætiøn") == True

    assert is_acceptable_word("s") == False
    assert is_acceptable_word("s ") == False
    assert is_acceptable_word("s!!!") == False
    assert is_acceptable_word("_s_") == False
    assert is_acceptable_word("1234") == False
    assert is_acceptable_word("1.123") == False
    assert is_acceptable_word("$$$$$$$") == False
    assert is_acceptable_word("___") == False

    assert is_acceptable_word_zh("你") == True

    assert is_acceptable_word_vi("đường") == True


def test_get_plain_text():

    assert TextProcessing.get_plain_text("This a <b>sample</b></b> text with HTML<p>tags</P>and<br>example.") == "This a sample text with HTML tags and example."
    assert TextProcessing.get_plain_text("This a <script> kk </script> example.") == "This a example."
    assert TextProcessing.get_plain_text("This N&amp;M that") == "This N&M that"
    assert TextProcessing.get_plain_text("Non-breaking space: This&nbsp;is&nbsp;a&nbsp;test.") == "Non-breaking space: This is a test."
    assert TextProcessing.get_plain_text("This [sound:azure-57d4ff9d-b02968eb-9f293f42-b1c6426f-2dd6b8a7.mp3]") == "This"
    assert TextProcessing.get_plain_text("Use of [brackets] <b>[inside HTML]</b> tags.") == "Use of [brackets] [inside HTML] tags."


def test_get_word_tokens_from_text_default_tokenizer_en():

    text_with_special_chars = "I can't \"believe\" it's here (wow) 1-character! 'amazinG'"
    assert TextProcessing.get_word_tokens_from_text(text_with_special_chars, LangId("en")) == ["can't", "believe", "it", "here", "wow", "1-character", "amazing"]

    assert TextProcessing.get_word_tokens_from_text("", LangId("en")) == []
    assert TextProcessing.get_word_tokens_from_text("12345", LangId("en")) == []

    assert TextProcessing.get_word_tokens_from_text("Simple sente-nce. EE.UU. Anna's visit. john's. o'clock", LangId("en")) == ['simple', 'sente-nce', 'ee.uu', 'anna', 'visit', 'john', 'o\'clock']
    assert TextProcessing.get_word_tokens_from_text("This is a\ttest.\t", LangId("en")) == ['this', 'is', 'test']
    assert TextProcessing.get_word_tokens_from_text("Hello, world!", LangId("en")) == ['hello', 'world']

    assert TextProcessing.get_word_tokens_from_text("Мне … лет.", LangId("en")) == ['мне', 'лет']
    assert TextProcessing.get_word_tokens_from_text("你跟我", LangId("en")) == ['你跟我']
    assert TextProcessing.get_word_tokens_from_text("أنا بصدّقك وإحنا دايماً منقلكم", LangId("en")) == ['أنا', 'بصدّقك', 'وإحنا', 'دايماً', 'منقلكم']


def test_get_word_tokens_from_text_user_tokenizer_th():
    # no support for tokenization, but Thai script should be accepted and not split
    assert TextProcessing.get_word_tokens_from_text("อาหาร hello", LangId("th")) == ['อาหาร']

def test_get_word_tokens_from_text_user_tokenizer_lo():
    # no support for tokenization, but Lao script should be accepted and not split
    assert TextProcessing.get_word_tokens_from_text("ຮັກ hello อาหาร", LangId("lo")) == ['ຮັກ']

def test_get_word_tokens_from_text_user_tokenizer_km():
    # no support for tokenization, but Khmer script should be accepted and not split
    assert TextProcessing.get_word_tokens_from_text("ជំរាបសួរ hello ຮັກ", LangId("km")) == ['ជំរាបសួរ']


def test_get_word_tokens_from_text_user_tokenizer_ja():

    if not USER_PROVIDED_TOKENIZERS.lang_has_tokenizer(LangId('ja')):
        print("User tokenizer for JA test skipped!!!")
        return

    for tokenizer in USER_PROVIDED_TOKENIZERS.get_all_tokenizers(LangId('ja')):
        print("User tokenizer for JA tested: "+tokenizer.__name__)
        assert TextProcessing.get_word_tokens_from_text("すもももももももものうち", LangId('ja'), tokenizer) == ['すもも', 'も', 'もも', 'も', 'もも', 'の', 'うち'], tokenizer.__name__
        assert TextProcessing.get_word_tokens_from_text("こんにちは。私の名前はシャンです。", LangId('ja'), tokenizer) == ["こんにちは", "私", "の", "名前", "は", "シャン", "です"], tokenizer.__name__
        assert TextProcessing.get_word_tokens_from_text("これはテストです。", LangId('ja'), tokenizer) == ["これ", "は", "テスト", "です"], tokenizer.__name__
        assert TextProcessing.get_word_tokens_from_text("私の名前は太郎です 。", LangId('ja'), tokenizer) == ["私", "の", "名前", "は", "太郎", "です"], tokenizer.__name__
        assert TextProcessing.get_word_tokens_from_text("あのイルカはとてもかわいい！", LangId('ja'), tokenizer) == ["あの", "イルカ", "は", "とても", "かわいい"], tokenizer.__name__
        assert TextProcessing.get_word_tokens_from_text("君の言葉は深いですね。", LangId('ja'), tokenizer) == ["君", "の", "言葉", "は", "深い", "です", "ね"], tokenizer.__name__


def test_get_word_tokens_from_text_user_tokenizer_zh():

    if not USER_PROVIDED_TOKENIZERS.lang_has_tokenizer(LangId('zh')):
        print("User tokenizer for ZH test skipped!!!")
        return

    for tokenizer in USER_PROVIDED_TOKENIZERS.get_all_tokenizers(LangId('zh')):
        print("User tokenizer for ZH tested: "+tokenizer.__name__)
        assert TextProcessing.get_word_tokens_from_text("你跟我", LangId('zh'), tokenizer) == ['你', '跟', '我'], tokenizer.__name__
        assert TextProcessing.get_word_tokens_from_text("hello 吃饭了吗😊? ", LangId('zh'), tokenizer) == ["吃饭", "了", "吗"], tokenizer.__name__
        assert TextProcessing.get_word_tokens_from_text("我爱自然语言处理。", LangId('zh'), tokenizer) == ['我', '爱', '自然语言', '处理'], tokenizer.__name__
        assert TextProcessing.get_word_tokens_from_text(" 我 爱自然语言处理。 ", LangId('zh'), tokenizer) == ['我', '爱', '自然语言', '处理'], tokenizer.__name__


def test_create_word_token():

    assert TextProcessing.create_word_token("$$hellO", LangId('en')) == "hello"
    assert TextProcessing.create_word_token("hello!", LangId('en')) == "hello"
    assert TextProcessing.create_word_token("we’ll", LangId('en')) == "we'll"
    assert TextProcessing.create_word_token("Iñtërnâtiônàlizætiøn", LangId('en')) == "iñtërnâtiônàlizætiøn"


def test_calc_word_presence_score():

    token_context = TextProcessing.get_word_tokens_from_text("test", LangId("en"))
    assert TextProcessing.calc_word_presence_score(token_context[0], token_context, 0) == 1.0

    token_context = TextProcessing.get_word_tokens_from_text("test abcd", LangId("en"))
    assert TextProcessing.calc_word_presence_score(token_context[0], token_context, 0) == (0.5+0.5+1)/3

    token_context = TextProcessing.get_word_tokens_from_text("test abcdabcd", LangId("en"))
    assert TextProcessing.calc_word_presence_score(token_context[0], token_context, 0) == (0.5+(1/3)+1)/3

    token_context = TextProcessing.get_word_tokens_from_text("test test abcd", LangId("en"))
    assert TextProcessing.calc_word_presence_score(token_context[0], token_context, 1) == ((2/3)+(2/3)+0.5)/3
