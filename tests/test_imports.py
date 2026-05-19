"""Lightweight import checks for package metadata and utilities."""


def test_package_imports():
    import solar_toolkit
    from solar_toolkit import path_config, solar_analysis_utils

    assert solar_toolkit.__version__ == "0.1.0"
    assert callable(path_config.load_script_config)
    assert callable(solar_analysis_utils.extract_time_from_filename)
