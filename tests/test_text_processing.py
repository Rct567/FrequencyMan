import re
from frequencyman.text_processing import TextProcessing

def test_acceptable_word():
    assert TextProcessing.acceptable_word("app-le") == True
    assert TextProcessing.acceptable_word("won't") == True
    assert TextProcessing.acceptable_word("s") == False

def test_get_plain_text():
    assert TextProcessing.get_plain_text("This a <b>sample</b></b> text with HTML<p>tags</P>and example.") == "This a sample text with HTML tags and example."

def test_get_word_tokens_from_text():

    # Test with a string that contains special characters
    text_with_special_chars = "I can't believe it's here (wow) 1-character!"
    assert TextProcessing.get_word_tokens_from_text(text_with_special_chars) == ["can't", "believe", "it's", "here", "wow", "1-character"]

    # Test with an empty string
    assert TextProcessing.get_word_tokens_from_text("") == []

