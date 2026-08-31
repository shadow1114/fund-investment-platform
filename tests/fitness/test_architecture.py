import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"


def _py_files(*parts: str) -> list[pathlib.Path]:
    root = SRC.joinpath(*parts)
    return sorted(root.rglob("*.py")) if root.exists() else []


def _imported_roots(path: pathlib.Path) -> set[str]:
    """返回该文件 import 的顶层模块名集合。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _dotted_imports(path: pathlib.Path) -> set[str]:
    """返回该文件 import 的完整点号路径集合。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module)
    return out


IO_LIBS = {
    "sqlalchemy", "psycopg", "psycopg2", "asyncpg", "alembic",
    "requests", "httpx", "aiohttp", "urllib", "akshare", "socket",
}

ML_LIBS = {
    "sklearn", "scikit_learn", "torch", "tensorflow", "keras",
    "xgboost", "lightgbm", "catboost", "transformers", "openai", "anthropic",
}


def test_strategy_library_has_no_io_dependency():
    """SDL-1 / PIT-A1：策略库不含数据访问实现，数据经注入的接口提供。"""
    offenders = [
        (f.relative_to(SRC), sorted(_imported_roots(f) & IO_LIBS))
        for f in _py_files("strategy_library")
        if _imported_roots(f) & IO_LIBS
    ]
    assert not offenders, f"strategy_library 出现 I/O 依赖：{offenders}"


def test_quant_engine_has_no_io_dependency():
    offenders = [
        (f.relative_to(SRC), sorted(_imported_roots(f) & IO_LIBS))
        for f in _py_files("quant_engine")
        if _imported_roots(f) & IO_LIBS
    ]
    assert not offenders, f"quant_engine 出现 I/O 依赖：{offenders}"


def test_no_ml_dependency_anywhere():
    """Constraint C-14：第一阶段不引入任何 ML / AI 技术栈。"""
    offenders = [
        (f.relative_to(SRC), sorted(_imported_roots(f) & ML_LIBS))
        for f in _py_files()
        if _imported_roots(f) & ML_LIBS
    ]
    assert not offenders, f"出现 ML / AI 依赖：{offenders}"


def test_strategy_library_has_no_runtime_mode_branch():
    """Constraint C-2 / SEI-3：策略库不感知运行模式，不得有『是否回测』分支。

    检查方式：SDL 中不得出现 is_backtest / runtime_mode / BACKTEST 这些名称。
    差异必须全部体现在注入的 decision_at 与 Data Context 上。
    """
    banned = {"is_backtest", "runtime_mode", "RuntimeMode", "BACKTEST"}
    offenders = []
    for f in _py_files("strategy_library"):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        hits = {
            node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in banned
        } | {
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr in banned
        }
        if hits:
            offenders.append((f.relative_to(SRC), sorted(hits)))
    assert not offenders, f"strategy_library 出现运行模式分支：{offenders}"


def test_portfolio_service_does_not_depend_on_factor_service():
    """DEP-3：保证 Return Estimate 与 Fund Score 两条数据流独立。

    portfolio-service 需要的是原始收益序列，不是因子值。
    """
    offenders = [
        f.relative_to(SRC)
        for f in _py_files("services", "portfolio_service")
        if any(m.startswith("fip.services.factor_service") for m in _dotted_imports(f))
    ]
    assert not offenders, f"portfolio_service 依赖了 factor_service：{offenders}"


def test_peer_group_module_does_not_depend_on_scoring_or_universe():
    """Constraint C-4：否则形成 Score → Universe → Peer Group → Score 的循环依赖。

    该循环不报错，但每次重算得到不同分数，直接破坏 NFR-REPRO-001。
    """
    banned_prefixes = (
        "fip.services.fund_service.scoring",
        "fip.services.fund_service.ranking",
        "fip.services.fund_service.universe",
    )
    offenders = []
    for f in _py_files("services", "fund_service", "peer_group"):
        bad = [m for m in _dotted_imports(f) if m.startswith(banned_prefixes)]
        if bad:
            offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"Peer Group 模块依赖了评分/候选池模块：{offenders}"


def test_platform_layer_does_not_import_services_at_module_level():
    """依赖方向单向：services → platform，不得反向。

    platform 内允许函数体内的延迟 import（如 PitDataContext.navs()），
    但不允许模块级 import —— 后者会形成真正的包级循环依赖。
    """
    offenders = []
    for f in _py_files("platform"):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in tree.body:  # 只看模块级语句
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            bad = [m for m in mods if m.startswith("fip.services")]
            if bad:
                offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"platform 层模块级依赖了 services 层：{offenders}"


@pytest.mark.parametrize("layer", ["strategy_library", "quant_engine"])
def test_layer_packages_exist(layer):
    """守卫测试：若目录被误删，上面的检查会静默通过（空集合恒满足）。"""
    assert (SRC / layer).is_dir(), f"{layer} 目录不存在，适应度测试将失去意义"
