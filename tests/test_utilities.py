import pytest

from frequencyman.lib.utilities import get_float, normalize_dict_floats_values, normalize_dict_positional_floats_values, remove_bottom_percent_dict, remove_trailing_commas_from_json

def test_normalize_dict_floats_values():

    result = normalize_dict_floats_values({ 'a': 2.0, 'b': 3.0, 'c': 7.0 })
    assert result['a'] < 0.0001 and result['a'] > 0
    assert result['c'] == 1

    result = normalize_dict_floats_values({ 'a': 0.0, 'b': 1.0})
    assert result['a'] == 0
    assert result['b'] == 1

def test_normalize_dict_floats_values_single_value():

    result = normalize_dict_floats_values({'a': 9999.0})
    assert result == {'a': 1.0}

    result = normalize_dict_floats_values({'a': 1.0})
    assert result == {'a': 1.0}

    result = normalize_dict_floats_values({'a': 0.9})
    assert result == {'a': 1.0}


def test_normalize_dict_floats_values_empty_dict():

    result = normalize_dict_floats_values({})
    assert result == {}

def test_normalize_dict_floats_values_all_zero_values():

    result = normalize_dict_floats_values({'a': 0.0, 'b': 0.0, 'c': 0.0})
    assert result == {'a': 0.0, 'b': 0.0, 'c': 0.0}

def test_normalize_dict_floats_values_negative_value():

    input_dict = {'a': -2.0, 'b': 1.0, 'c': 3.0}

    with pytest.raises(Exception, match="Unexpected below zero value found."):
        normalize_dict_floats_values(input_dict)

def test_get_float_none():

    assert get_float(None) is None

def test_get_float_float():

    assert get_float(3.14) == 3.14
    assert get_float(0.0) == 0.0

def test_get_float_int():

    assert get_float(42) == 42.0
    assert get_float(0) == 0.0

def test_get_float_string_numeric():

    assert get_float("3.14") == 3.14
    assert get_float("42") == 42.0
    assert get_float("0.0") == 0.0

def test_get_float_string_non_numeric():

    assert get_float("") is None
    assert get_float("hello") is None
    assert get_float("3.14.15") is None
    assert get_float("3.14a") is None
    assert get_float("a3.14") is None


def test_normalize_dict_positional_floats_values_empty_dict():

    assert normalize_dict_positional_floats_values({}) == {}

def test_normalize_dict_positional_floats_values_dict():

    assert normalize_dict_positional_floats_values({'a': 1.0}) == {'a': 1.0}
    assert normalize_dict_positional_floats_values({'a': 2.0, 'b': 1.0, 'c': 0.5}) == {'a': 1.0, 'b': 2/3, 'c': 1/3}
    assert normalize_dict_positional_floats_values({'a': 2.0, 'b': 1.1, 'c': 1.0, 'd': 0.5}) == {'a': 1.0, 'b': 3/4, 'c': 2/4, 'd': 1/4}


def test_normalize_dict_positional_floats_values_same_values():

    assert normalize_dict_positional_floats_values({'a': 2.0, 'b': 1.0, 'c': 1.0, 'd': 0.5}) == {'a': 1.0, 'b': 2/3, 'c': 2/3, 'd': 1/3}
    assert normalize_dict_positional_floats_values({'a': 1.0, 'b': 1.0}) == {'a': 1.0, 'b': 1.0}
    assert normalize_dict_positional_floats_values({'a': 1.0, 'b': 1.0, 'c': 0.1}) == {'a': 1.0, 'b': 1.0, 'c': 1/2}


def test_normalize_dict_positional_floats_values_not_desc_sorted():

    with pytest.raises(AssertionError):
        normalize_dict_positional_floats_values({'a': 1.0, 'b': 2.0, 'c': 3.0})

def test_remove_bottom_percent_dict():

    result = remove_bottom_percent_dict({"a": 4, "b": 3, "c": 2, "d": 1}, 0.5, 0)
    assert result == {"a": 4, "b": 3}

    result = remove_bottom_percent_dict({"a": 4, "b": 3, "c": 2, "d": 1}, 0.5, 3)
    assert result == {"a": 4, "b": 3, "c": 2}

    result = remove_bottom_percent_dict({"a": 4, "b": 3, "c": 2, "d": 1}, 1.0, 1)
    assert result == {"a": 4}

    result = remove_bottom_percent_dict({"a": 4, "b": 3, "c": 2, "d": 1}, 0.9, 0)
    assert result == {}

    result = remove_bottom_percent_dict({"a": 4, "b": 3, "c": 2, "d": 1}, 0.5, 9999)
    assert result == {"a": 4, "b": 3, "c": 2, "d": 1}

    result = remove_bottom_percent_dict({"a": 4, "b": 3, "c": 2, "d": 1}, 0.0, 9999)
    assert result == {"a": 4, "b": 3, "c": 2, "d": 1}

    result = remove_bottom_percent_dict({"a": 4, "b": 3, "c": 2, "d": 1}, 0.25, 0)
    assert result == {"a": 4, "b": 3, "c": 2}


def test_remove_trailing_commas_from_json():

    test_json_str = r'''
    [
        123, true, false, null, {",": ", "},
        {
            "\n\\\",]\\": "\n\\\",]\\",
            "\n\\\",}\\": "\n\\\",}\\",
        },
    ]
    '''

    assert remove_trailing_commas_from_json(test_json_str) == r'''
    [
        123, true, false, null, {",": ", "},
        {
            "\n\\\",]\\": "\n\\\",]\\",
            "\n\\\",}\\": "\n\\\",}\\"
        }
    ]
    '''

