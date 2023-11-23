import os
import pytest
from frequencyman.word_frequency_list import LangKey, WordFrequencyLists


LIST_DIR = os.path.join(os.path.dirname(__file__), 'data', 'word_frequency_lists')


@pytest.fixture
def word_frequency_lists():
    return WordFrequencyLists(LIST_DIR)


def test_load_frequency_lists(word_frequency_lists: WordFrequencyLists):

    keys = [LangKey('en'), LangKey('es')]
    word_frequency_lists.load_frequency_lists(keys)

    for key in keys:
        assert key in word_frequency_lists


def test_get_word_frequency(word_frequency_lists: WordFrequencyLists):

    word_frequency_lists.load_frequency_lists([LangKey('en'), LangKey('es')])

    frequency = word_frequency_lists.get_word_frequency(LangKey('en'), 'aaa', default=-1.0)
    assert frequency == 1

    frequency = word_frequency_lists.get_word_frequency(LangKey('en'), 'bbb', default=-1.0)
    assert frequency == 2/3

    frequency = word_frequency_lists.get_word_frequency(LangKey('en'), 'ccc', default=-1.0)
    assert frequency == 1/3

def test_get_word_frequency_from_combined_files(word_frequency_lists: WordFrequencyLists):

    word_frequency_lists.load_frequency_lists([LangKey('jp')])

    frequency = word_frequency_lists.get_word_frequency(LangKey('jp'), 'aaaa', default=-1.0)
    assert frequency == 1

    frequency = word_frequency_lists.get_word_frequency(LangKey('jp'), 'bbbb', default=-1.0)
    assert frequency == 7/8


def test_key_has_frequency_list_file(word_frequency_lists: WordFrequencyLists):

    keys_with_files = [LangKey('en'), LangKey('es')]
    keys_without_files = [LangKey('fr'), LangKey('de'), LangKey('it')]

    for key in keys_with_files:
        assert word_frequency_lists.key_has_frequency_list_file(key)

    assert word_frequency_lists.keys_have_frequency_list_file(keys_with_files)

    # test files not exist

    for key in keys_without_files:
        assert not word_frequency_lists.key_has_frequency_list_file(key)

    assert not word_frequency_lists.keys_have_frequency_list_file(keys_without_files)


def test_invalid_lists_directory():

    with pytest.raises(ValueError, match="directory"):
        WordFrequencyLists('/invalid/directory/path')


def test_list_not_yet_loaded(word_frequency_lists: WordFrequencyLists):

    with pytest.raises(Exception, match="No word frequency lists loaded"):
        word_frequency_lists.get_word_frequency(LangKey('en'), 'aaa', default=-1.0)
