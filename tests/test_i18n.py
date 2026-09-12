import utils


def test_all_i18n_keys_have_russian_and_english_text() -> None:
    for key, variants in utils.i18n._TEXTS.items():
        assert utils.UI_RU in variants, key
        assert utils.UI_EN in variants, key
        assert variants[utils.UI_RU].strip(), key
        assert variants[utils.UI_EN].strip(), key