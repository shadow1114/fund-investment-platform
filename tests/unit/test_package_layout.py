import importlib

import fip


def test_version_is_set():
    assert fip.__version__ == "0.1.0"


def test_platform_subpackage_does_not_shadow_stdlib():
    """fip.platform 必须嵌套在 fip 下，否则会遮蔽标准库 platform。"""
    import platform as stdlib_platform

    assert hasattr(stdlib_platform, "python_version")
    fip_platform = importlib.import_module("fip.platform")
    assert fip_platform is not stdlib_platform


def test_all_layer_packages_importable():
    for name in [
        "fip.quant_engine",
        "fip.strategy_library",
        "fip.platform.db",
        "fip.platform.decision_data",
        "fip.platform.source",
        "fip.platform.jobs",
        "fip.platform.config",
        "fip.services.data_service",
        "fip.services.factor_service",
        "fip.services.fund_service",
        "fip.services.portfolio_service",
        "fip.services.backtest_service",
    ]:
        importlib.import_module(name)


def test_settings_has_database_urls():
    from fip.settings import settings

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.test_database_url.startswith("postgresql+psycopg://")
