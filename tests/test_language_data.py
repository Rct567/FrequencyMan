from math import exp
import os
import pytest
from frequencyman.language_data import LangDataId, LanguageData


LIST_DIR = os.path.join(os.path.dirname(__file__), 'data', 'lang_data_test', 'lang_data')


@pytest.fixture
def lang_data():
    return LanguageData(LIST_DIR)


def test_load_lang_data(lang_data: LanguageData):

    lang_data_ids = {LangDataId('en'), LangDataId('es')}
    lang_data.load_data(lang_data_ids)

    assert lang_data.word_frequency_lists.word_frequency_lists is not None
    assert len(lang_data.word_frequency_lists.word_frequency_lists.keys()) == len(lang_data_ids)

    assert lang_data.ignore_lists.ignore_lists is not None
    assert len(lang_data.ignore_lists.ignore_lists.keys()) == len(lang_data_ids)

    for lang_data_id in lang_data_ids:
        assert lang_data_id in lang_data.word_frequency_lists.word_frequency_lists
        assert lang_data.id_has_directory(lang_data_id)


def test_get_word_frequency(lang_data: LanguageData):

    lang_data.load_data({LangDataId('en'), LangDataId('es')})

    expected_fr_values = {
        'aaa': 1,
        'bbb': 2/3,
        'ccc': 1/3,
        'none_existing': -1.0
    }

    for word, expected_value in expected_fr_values.items():
        value = lang_data.get_word_frequency(LangDataId('en'), word, default=-1.0)
        assert value == expected_value, f"Expected '{word}' to have frequency '{expected_value}' but got '{value}'"


def test_get_word_frequency_from_combined_files(lang_data: LanguageData):

    lang_data.load_data({LangDataId('jp')})

    assert lang_data.word_frequency_lists.word_frequency_lists is not None
    assert len(lang_data.word_frequency_lists.get_files_by_id(LangDataId('jp'))) == 2

    expected_fr_values = {
        'aaaa': 1,
        'cccc': 1,
        'bbbb': 6/7,
        'dddd': 5/7,
        'eeee': 4/7,
        'ffff': 3/7,
        'gggg': 2/7,
        'hhhh': 1/7,
        'none_existing': -1.0
    }

    for word, expected_value in expected_fr_values.items():
        value = lang_data.get_word_frequency(LangDataId('jp'), word, default=-1.0)
        assert value == expected_value, f"Expected '{word}' to have frequency '{expected_value}' but got '{value}'"


def test_id_has_frequency_list_file(lang_data: LanguageData):

    ids_with_files = {LangDataId('en'), LangDataId('es')}
    ids_without_files = {LangDataId('fr'), LangDataId('de'), LangDataId('it')}

    for lang_data_id in ids_with_files:
        assert lang_data.word_frequency_lists.id_has_list_file(lang_data_id)

    for lang_data_id in ids_without_files:
        assert not lang_data.word_frequency_lists.id_has_list_file(lang_data_id)


def test_frequency_list_csv_file(lang_data: LanguageData):

    lang_data.load_data({LangDataId('ru')})

    assert lang_data.word_frequency_lists.word_frequency_lists is not None
    assert len(lang_data.word_frequency_lists.get_files_by_id(LangDataId('ru'))) == 1

    frequency = lang_data.get_word_frequency(LangDataId('ru'), 'иии', default=-1.0)
    assert frequency == 1

    frequency = lang_data.get_word_frequency(LangDataId('ru'), 'ввв', default=-1.0)
    assert frequency == 4/5

    frequency = lang_data.get_word_frequency(LangDataId('ru'), 'чточто', default=-1.0)
    assert frequency == 1/5


def test_id_has_ignore_file(lang_data: LanguageData):

    ids_with_files = {LangDataId('jp')}
    ids_without_files = {LangDataId('fr'), LangDataId('de'), LangDataId('it'), LangDataId('es')}

    for lang_data_id in ids_with_files:
        assert lang_data.ignore_lists.id_has_list_file(lang_data_id)

    for lang_data_id in ids_without_files:
        assert not lang_data.ignore_lists.id_has_list_file(lang_data_id)


def test_is_ignore_word(lang_data: LanguageData):

    lang_data.load_data({LangDataId('jp')})

    assert lang_data.ignore_lists.ignore_lists is not None
    assert len(lang_data.ignore_lists.get_files_by_id(LangDataId('jp'))) == 2

    assert lang_data.is_ignore_word(LangDataId('jp'), 'yes')
    assert lang_data.is_ignore_word(LangDataId('jp'), 'yes_with_trailing_space')
    assert lang_data.is_ignore_word(LangDataId('jp'), 'from_second_file')
    assert not lang_data.is_ignore_word(LangDataId('jp'), 'no')


def test_invalid_lists_directory():

    with pytest.raises(ValueError, match="directory"):
        LanguageData('/invalid/directory/path')


def test_list_not_yet_loaded(lang_data: LanguageData):

    with pytest.raises(Exception, match="No word frequency lists loaded"):
        lang_data.get_word_frequency(LangDataId('en'), 'aaa', default=-1.0)
