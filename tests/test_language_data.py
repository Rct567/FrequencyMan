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

    value = lang_data.get_word_frequency(LangDataId('en'), 'aaa', default=-1.0)
    assert value == 1

    value_b = lang_data.get_word_frequency(LangDataId('en'), 'bbb', default=-1.0)
    assert 0 < value_b < 1

    value_c = lang_data.get_word_frequency(LangDataId('en'), 'ccc', default=-1.0)
    assert 0 < value_c < value_b

    value = lang_data.get_word_frequency(LangDataId('en'), 'none_existing', default=-1.0)
    assert value == -1.0


def test_get_word_frequency_from_combined_files(lang_data: LanguageData):

    lang_data.load_data({LangDataId('jp')})

    assert lang_data.word_frequency_lists.word_frequency_lists is not None
    assert len(lang_data.word_frequency_lists.get_files_by_id(LangDataId('jp'))) == 2

    value = lang_data.get_word_frequency(LangDataId('jp'), 'aaaa', default=-1.0)
    assert value == 1

    value = lang_data.get_word_frequency(LangDataId('jp'), 'cccc', default=-1.0)
    assert value == 1

    value_a = lang_data.get_word_frequency(LangDataId('jp'), 'bbbb', default=-1.0)
    assert 0 < value_a < 1

    value_b = lang_data.get_word_frequency(LangDataId('jp'), 'dddd', default=-1.0)
    assert 0 < value_b < value_a

    value_c = lang_data.get_word_frequency(LangDataId('jp'), 'hhhh', default=-1.0)
    assert 0 < value_c < value_b

    value = lang_data.get_word_frequency(LangDataId('jp'), 'none_existing', default=-1.0)
    assert value == -1.0


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

    value_a = lang_data.get_word_frequency(LangDataId('ru'), 'иии', default=-1.0)
    assert 0 < value_a == 1

    value_b = lang_data.get_word_frequency(LangDataId('ru'), 'ввв', default=-1.0)
    assert 0 < value_b < value_a

    value_c = lang_data.get_word_frequency(LangDataId('ru'), 'чточто', default=-1.0)
    assert 0 < value_c < value_b


def test_id_has_ignore_file(lang_data: LanguageData):

    ids_with_files = {LangDataId('jp')}
    ids_without_files = {LangDataId('fr'), LangDataId('de'), LangDataId('it'), LangDataId('es')}

    for lang_data_id in ids_with_files:
        assert lang_data.ignore_lists.id_has_list_file(lang_data_id)

    for lang_data_id in ids_without_files:
        assert not lang_data.ignore_lists.id_has_list_file(lang_data_id)


def test_ignored_words(lang_data: LanguageData):

    lang_data.load_data({LangDataId('jp')})

    assert lang_data.ignore_lists.ignore_lists is not None
    assert len(lang_data.ignore_lists.get_files_by_id(LangDataId('jp'))) == 2

    ignore_list = lang_data.get_ignore_list(LangDataId('jp'))
    ignored_words = lang_data.get_ignored_words(LangDataId('jp'))

    assert ignore_list == {'yes', 'yes_with_trailing_space', 'from_second_file'}
    assert ignored_words == {'yes', 'yes_with_trailing_space', 'from_second_file', 'word_from_names_list_in_lang_data_dir'}


def test_invalid_lists_directory():

    with pytest.raises(ValueError, match="directory"):
        LanguageData('/invalid/directory/path')


def test_list_not_yet_loaded(lang_data: LanguageData):

    with pytest.raises(Exception, match="No word frequency lists loaded"):
        lang_data.get_word_frequency(LangDataId('en'), 'aaa', default=-1.0)
