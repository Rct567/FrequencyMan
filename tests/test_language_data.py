import os
import pytest
from frequencyman.language_data import LangDataId, LanguageData


LIST_DIR = os.path.join(os.path.dirname(__file__), 'data', 'lang_data_test')


@pytest.fixture
def lang_data():
    return LanguageData(LIST_DIR)


def test_load_frequency_lists(lang_data: LanguageData):

    keys = [LangDataId('en'), LangDataId('es')]
    lang_data.load_frequency_lists(keys)

    for key in keys:
        assert lang_data.word_frequency_lists is not None and key in lang_data.word_frequency_lists


def test_get_word_frequency(lang_data: LanguageData):

    lang_data.load_frequency_lists([LangDataId('en'), LangDataId('es')])

    frequency = lang_data.get_word_frequency(LangDataId('en'), 'aaa', default=-1.0)
    assert frequency == 1

    frequency = lang_data.get_word_frequency(LangDataId('en'), 'bbb', default=-1.0)
    assert frequency == 2/3

    frequency = lang_data.get_word_frequency(LangDataId('en'), 'ccc', default=-1.0)
    assert frequency == 1/3


def test_get_word_frequency_from_combined_files(lang_data: LanguageData):

    lang_data.load_frequency_lists([LangDataId('jp')])

    frequency = lang_data.get_word_frequency(LangDataId('jp'), 'aaaa', default=-1.0)
    assert frequency == 1

    frequency = lang_data.get_word_frequency(LangDataId('jp'), 'bbbb', default=-1.0)
    assert frequency == 7/8


def test_key_has_frequency_list_file(lang_data: LanguageData):

    keys_with_files = [LangDataId('en'), LangDataId('es')]
    keys_without_files = [LangDataId('fr'), LangDataId('de'), LangDataId('it')]

    for key in keys_with_files:
        assert lang_data.key_has_frequency_list_file(key)

    assert lang_data.keys_have_frequency_list_file(keys_with_files)

    # test files not exist

    for key in keys_without_files:
        assert not lang_data.key_has_frequency_list_file(key)

    assert not lang_data.keys_have_frequency_list_file(keys_without_files)


def test_invalid_lists_directory():

    with pytest.raises(ValueError, match="directory"):
        LanguageData('/invalid/directory/path')


def test_list_not_yet_loaded(lang_data: LanguageData):

    with pytest.raises(Exception, match="No word frequency lists loaded"):
        lang_data.get_word_frequency(LangDataId('en'), 'aaa', default=-1.0)
