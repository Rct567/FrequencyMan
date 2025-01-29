import os
import pytest
from frequencyman.language_data import LangDataId, LanguageData, WordFrequencyLists


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

    word_frequency_list = lang_data.get_word_frequency_list(LangDataId('en'))

    value = word_frequency_list.get('aaa', -1.0)
    assert value == 1

    value_b = word_frequency_list.get('bbb', -1.0)
    assert 0 < value_b < 1

    value_c = word_frequency_list.get('ccc', -1.0)
    assert 0 < value_c < value_b

    value = word_frequency_list.get('none_existing', -1.0)
    assert value == -1.0


def test_get_word_frequency_from_combined_files(lang_data: LanguageData):

    word_frequency_list = lang_data.get_word_frequency_list(LangDataId('jp'))

    assert lang_data.word_frequency_lists.word_frequency_lists is not None

    assert len(lang_data.word_frequency_lists.get_files_by_id(LangDataId('jp'))) == 2

    value = word_frequency_list.get('aaaa', -1.0)
    assert value == 1

    value = word_frequency_list.get('cccc', -1.0)
    assert value == 1

    value_a = word_frequency_list.get('bbbb', -1.0)
    assert 0 < value_a < 1

    value_b = word_frequency_list.get('dddd', -1.0)
    assert 0 < value_b < value_a

    value_c = word_frequency_list.get('hhhh',-1.0)
    assert 0 < value_c < value_b

    value = word_frequency_list.get('none_existing', -1.0)
    assert value == -1.0


def test_id_has_frequency_list_file(lang_data: LanguageData):

    ids_with_files = {LangDataId('en'), LangDataId('es')}
    ids_without_files = {LangDataId('fr'), LangDataId('lt'), LangDataId('it')}

    for lang_data_id in ids_with_files:
        assert lang_data.word_frequency_lists.id_has_list_file(lang_data_id)

    for lang_data_id in ids_without_files:
        assert not lang_data.word_frequency_lists.id_has_list_file(lang_data_id)


def test_frequency_list_csv_file(lang_data: LanguageData):

    word_frequency_list = lang_data.get_word_frequency_list(LangDataId('ru'))  # csv file

    assert lang_data.word_frequency_lists.word_frequency_lists is not None
    assert len(lang_data.word_frequency_lists.get_files_by_id(LangDataId('ru'))) == 1

    value_a = word_frequency_list.get('иии', -1.0)
    assert value_a == 1

    value_b = word_frequency_list.get('ввв', -1.0)
    assert 0 < value_b < value_a

    value_c = word_frequency_list.get('чточто', -1.0)
    assert 0 < value_c < value_b


def test_frequency_list_csv_anki_morphs_priority_file(lang_data: LanguageData):

    word_frequency_list = lang_data.get_word_frequency_list(LangDataId('de')) # anki morphs priority file

    value_a = word_frequency_list.get('hat', -1.0)
    assert 0 < value_a < 1

    value_b = word_frequency_list.get('hatte', -1.0)
    assert 0 < value_b < value_a


def test_id_has_ignore_file(lang_data: LanguageData):

    ids_with_files = {LangDataId('jp')}
    ids_without_files = {LangDataId('fr'), LangDataId('de'), LangDataId('it'), LangDataId('es')}

    for lang_data_id in ids_with_files:
        assert lang_data.ignore_lists.id_has_list_file(lang_data_id)

    for lang_data_id in ids_without_files:
        assert not lang_data.ignore_lists.id_has_list_file(lang_data_id)


def test_ignored_words(lang_data: LanguageData):

    ignore_list = lang_data.get_ignore_list(LangDataId('jp'))
    ignored_words = lang_data.get_ignored_words(LangDataId('jp'))

    assert lang_data.ignore_lists.ignore_lists is not None
    assert len(lang_data.ignore_lists.get_files_by_id(LangDataId('jp'))) == 2

    assert ignore_list == {'yes', 'yes_with_trailing_space', 'from_second_file'}
    assert ignored_words == {'yes', 'yes_with_trailing_space', 'from_second_file', 'word_from_names_list_in_lang_data_dir'}


def test_invalid_lists_directory():

    with pytest.raises(ValueError, match="directory"):
        LanguageData('/invalid/directory/path')



# Tests for combine_lists_by_top_position

combine_lists_by_top_position = WordFrequencyLists.combine_lists_by_top_position


def test_combine_lists_by_top_position_empty():

    result = combine_lists_by_top_position([])
    assert result == {}


def test_combine_lists_by_top_position_single_list():

    result = combine_lists_by_top_position([[('a', 1)]])
    assert result == {'a': 1}


def test_combine_lists_by_top_position_multiple_lists_same_word():

    result = combine_lists_by_top_position([
        [('a', 2)],
        [('a', 1)],
    ])
    assert result == {'a': 1}


def test_combine_lists_by_top_position_multiple_lists_same_values():

    result = combine_lists_by_top_position([
        [('a', 2), ('c', 2)],
        [('b', 2), ('d', 2)],
    ])
    assert result == {'a': 2, 'b': 2, 'c': 2, 'd': 2}


def test_combine_lists_by_top_position_word_in_some_lists():

    result = combine_lists_by_top_position([
        [('a', 1), ('b', 3)],
        [('a', 2), ('c', 4)],
    ])
    assert result == {'a': 1, 'b': 3, 'c': 4}


def test_combine_lists_by_top_position_duplicate_in_same_list():

    result = combine_lists_by_top_position([
        [('a', 3), ('a', 2), ('b', 5)],
        [('a', 1)],
    ])
    assert result == {'a': 1, 'b': 5}


# Tests for combine_lists_by_avg_position

combine_lists_by_avg_position = WordFrequencyLists.combine_lists_by_avg_position


def test_combine_lists_by_avg_position_empty():

    result = combine_lists_by_avg_position([])
    assert result == {}


def test_combine_lists_by_avg_position_single_list():

    result = combine_lists_by_avg_position([[('a', 2), ('b', 5)]])
    assert result == {'a': 2, 'b': 5}


def test_combine_lists_by_avg_position_missing_word():

    result = combine_lists_by_avg_position([
        [('a', 2)],
        [('b', 5)],
    ])
    assert result == {'a': 4, 'b': 5}


def test_combine_lists_by_avg_position_three_lists():

    result = combine_lists_by_avg_position([
        [('a', 3)],
        [('a', 5)],
        [('b', 10), ('c', 100)],
    ])
    assert result == {'a': 36, 'b': 70, 'c': 100}


def test_combine_lists_by_avg_position_three_lists_same_values():

        result = combine_lists_by_avg_position([
            [('a', 1), ('x', 50)],
            [('b', 1), ('x', 50)],
        ])
        assert result == {'a': 26, 'b': 26, 'x': 50}


def test_combine_lists_by_avg_position_order():

    result = combine_lists_by_avg_position([
        [('a', 4), ('b', 6)],
        [('a', 6), ('b', 4)],
    ])
    assert result == {'a': 5, 'b': 5}


def test_combine_lists_by_avg_position_lowest_position():

    result = combine_lists_by_avg_position([
        [('m', 5)],
        [],
        [],
    ])
    assert result == {'m': 5}
