from config.loader import get_settings

def test_settings_load():
    settings = get_settings()
    assert settings.app.target_package_id == "com.nextbillion.groww"
    assert settings.theming.max_themes == 5
    assert settings.theming.top_themes_in_pulse == 3
    assert settings.pulse.max_words == 250
    assert settings.pulse.required_verbatim_quotes == 3
    assert len(settings.theming.taxonomy) == 5
