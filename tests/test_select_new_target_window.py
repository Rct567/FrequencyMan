from frequencyman.ui.select_new_target_window import SelectNewTargetWindow

class TestSelectNewTargetWindow:

    def test_get_lang_data_id_suggestion(self):

        assert SelectNewTargetWindow.get_lang_data_id_suggestion("sentence", "My note type", "My deck") == ""
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Front", "My note type", "My deck") == ""
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Back", "My note type", "My deck") == ""

        assert SelectNewTargetWindow.get_lang_data_id_suggestion("sentence", "My note type", "My Spanish deck") == "es"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("sentence", "My Spanish note type", "My deck") == "es"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Spanish", "My note type", "My deck") == "es"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Spanish", "German", "Korean") == "es"

        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Korean", "My note type", "My deck") == "ko"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Word", "My note type", "My Korean deck") == "ko"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Sentence", "My note type", "My Korean deck") == "ko"

        assert SelectNewTargetWindow.get_lang_data_id_suggestion("中文释义", "My note type", "My deck") == "zh"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("汉语翻译", "My note type", "My Chinese deck") == "zh"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("英语单词", "My note type", "My Chinese deck") == "en"

        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Translation", "My Korean note type", "My Korean deck") == "en"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("Meaning", "My Korean note type", "My Korean deck") == "en"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("en", "My Korean note type", "My Korean deck") == "en"
        assert SelectNewTargetWindow.get_lang_data_id_suggestion("en_word", "My Korean note type", "My Korean deck") == "en"

