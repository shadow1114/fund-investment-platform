"""架构适应度测试。

本文件覆盖的约束：
- SDL-1 / PIT-A1：strategy_library / quant_engine 无 I/O 依赖
- C-2 / SEI-3：strategy_library 无运行模式分支
- C-14：全仓库无 ML / AI 依赖
- DEP-3：portfolio_service 不依赖 factor_service
- C-4：peer_group 模块不依赖 scoring / ranking / universe
- 依赖方向单向：platform 层不在模块级依赖 services 层

明确不覆盖：
- C-3（backend service 层不得含投资策略规则、阈值或常量）—— 语义上 AST 无法判定
  「业务阈值」与「无害配置常量」（如分页大小、超时时间）的区别，写一条弱正则只会
  产生大量误报，最终被人关闭，比没有测试更糟。C-3 由 code review 保障，非机器可检。
"""

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"


def _py_files(*parts: str) -> list[pathlib.Path]:
    """返回给定子路径下的所有 .py 文件。

    调用方传入的 parts 不带扩展名（如 "peer_group"），因为该模块目前预期是一个包
    （`peer_group/__init__.py` ...）。但若它日后落成单文件模块 `peer_group.py`，
    `SRC.joinpath(*parts)` 得到的仍是不带扩展名的路径、既不是目录也不直接是文件 ——
    对着它调用 rglob 或直接判 is_file() 都会静默返回 []，让检查永久性地失去意义。
    因此显式尝试三种情形：路径是目录 → rglob 递归收集；路径本身不存在但
    `<路径>.py` 存在 → 视为单文件模块，返回该文件；否则 → []。
    """
    root = SRC.joinpath(*parts)
    if root.is_dir():
        return sorted(root.rglob("*.py"))
    single_file = root.with_suffix(".py")
    if single_file.is_file():
        return [single_file]
    return []


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
    """返回该文件 import 的完整点号路径集合。

    对 `from a.b import c` 既记录 `a.b`（module 本身），也记录 `a.b.c`
    （逐个 alias 拼接） —— 否则 `from fip.services import factor_service` 这类
    惯用写法只会留下 `fip.services`，检查『是否依赖 fip.services.factor_service』
    时永远命中不了。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module)
            out.update(f"{node.module}.{alias.name}" for alias in node.names)
    return out


def _touches(module: str, prefix: str) -> bool:
    """判断 `module` 是否『命中』`prefix` —— 必须落在点边界上，而非裸前缀匹配。

    裸 `str.startswith(prefix)` 会把 `fip.services.factor_service_utils`
    误判为依赖 `fip.services.factor_service`（仅仅共享字符串前缀，并非同一
    模块也不是其子模块）。一条会对无关模块报警的适应度测试，比一条过窄的
    测试更糟——开发者遇到的第一反应通常是直接关掉它。
    """
    return module == prefix or module.startswith(prefix + ".")


@pytest.mark.parametrize(
    ("module", "prefix", "expected"),
    [
        # 精确相等
        ("fip.services.factor_service", "fip.services.factor_service", True),
        # 子模块
        ("fip.services.factor_service.x", "fip.services.factor_service", True),
        # 仅共享字符串前缀，不落在点边界上 —— round-1 的回归就出在这类输入上，
        # 必须锁死为 False（否则又退化回裸 startswith）。
        ("fip.services.factor_service_utils", "fip.services.factor_service", False),
        # 父包本身不算依赖子模块
        ("fip.services", "fip.services.factor_service", False),
    ],
)
def test_touches_matches_on_dot_boundary_only(module: str, prefix: str, expected: bool):
    """锁死 _touches 的点边界语义，防止再退化回裸 str.startswith。

    Round-1 fix 把 `_dotted_imports` 改成同时记录 alias 拼接后的完整路径，
    但两处消费者当时仍用裸前缀比较，导致 `fip.services.factor_service_utils`
    被误判为依赖 `fip.services.factor_service` —— 仅仅共享字符串前缀，并非
    同一模块也不是其子模块。这条测试直接对 `_touches` 断言，不依赖任何
    文件系统探针；探针验证的是『今天』修复生效，这里锁住的是『明天』不
    退化。
    """
    assert _touches(module, prefix) is expected


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

    检查方式：SDL 中不得出现 is_backtest / runtime_mode / BACKTEST 这些名称，
    也不得以同名字符串字面量出现（例如 `if mode == "BACKTEST":`）——
    这是该分支最常见的惯用写法，只查 Name / Attribute 抓不到它。
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
        } | {
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in banned
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
        if any(_touches(m, "fip.services.factor_service") for m in _dotted_imports(f))
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
        bad = [
            m for m in _dotted_imports(f)
            if any(_touches(m, prefix) for prefix in banned_prefixes)
        ]
        if bad:
            offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"Peer Group 模块依赖了评分/候选池模块：{offenders}"


def test_platform_layer_does_not_import_services_at_module_level():
    """依赖方向单向：services → platform，不得反向。

    platform 内允许函数体内的延迟 import（如 PitDataContext.navs()），
    但不允许模块级 import —— 后者会形成真正的包级循环依赖。

    必须同时识别绝对导入（`import fip.services...` /
    `from fip.services... import x`）与相对导入（`from ...services.x import y`）。
    相对导入的 `node.module` 不带 `fip.` 前缀（例如上例中 `node.module ==
    "services.data_service"`、`node.level == 3`），只匹配 `fip.services` 前缀
    会把这类写法完全放过 —— 而模块级相对导入正是本测试要防的典型违规形式。

    还必须处理相对导入裸包名的形式，如 `from .. import services`：这类语句的
    `node.module` 是 `None`（包名落在 `node.names` 里而不是 `node.module` 里），
    朴素的 `node.module and ...` 判断会因 `module` 为假值而整体短路放过它。
    """
    offenders = []
    for f in _py_files("platform"):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in tree.body:  # 只看模块级语句
            bad: list[str] = []
            if isinstance(node, ast.Import):
                bad = [a.name for a in node.names if _touches(a.name, "fip.services")]
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    if node.module:
                        # 相对导入且带 module：如 `from ...services.x import y`。
                        # module 本身不带 fip. 前缀，需按首段判断。
                        if node.module.split(".")[0] == "services":
                            bad = [f"{'.' * node.level}{node.module}"]
                    else:
                        # 相对导入且 module 为 None：包名在 names 里，
                        # 如 `from .. import services`。
                        bad = [
                            f"{'.' * node.level}{a.name}"
                            for a in node.names
                            if a.name == "services"
                        ]
                elif node.module and _touches(node.module, "fip.services"):
                    bad = [node.module]
            if bad:
                offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"platform 层模块级依赖了 services 层：{offenders}"


GUARDED_ROOTS: list[tuple[str, ...]] = [
    ("strategy_library",),
    ("quant_engine",),
    ("services", "portfolio_service"),
    ("platform",),
]


@pytest.mark.parametrize("parts", GUARDED_ROOTS, ids=lambda p: "/".join(p))
def test_scanned_roots_exist(parts: tuple[str, ...]):
    """守卫测试：若被扫目录被误删或改名，上面的检查会静默通过（空集合恒满足）。

    覆盖上面各检查实际扫描的每一个根目录（peer_group 除外，见下方独立的
    可见 skip 占位测试 —— 它尚未创建，不能对一个不存在的目录做 is_dir 断言）。
    """
    root = SRC.joinpath(*parts)
    assert root.is_dir(), f"{'/'.join(parts)} 目录不存在，适应度测试将失去意义"


def test_peer_group_guard_is_visible_not_silent():
    """C-4 检查（test_peer_group_module_does_not_depend_on_scoring_or_universe）
    扫描 services/fund_service/peer_group，但该模块要到 Plan-3（M1.5）才会创建
    （见实现计划『缺口』附录：B1/B2/B3 决策边界产生于 Peer Group / Universe /
    Optimization，三者在 Plan-1 中均不存在）。

    在它落地之前，C-4 检查处于 100% vacuous 状态且没有任何警报 —— 这条测试就是
    那个警报：用可见的 skip 顶替沉默的通过，防止误以为 C-4 已被自动强制执行。

    一旦 services/fund_service/peer_group 出现（无论是包还是单文件模块），
    本测试应立即失败，提醒把它补进 GUARDED_ROOTS（包形式）或确认 _py_files
    的单文件探测已覆盖它（单文件形式），然后删除本占位测试。
    """
    pkg = SRC / "services" / "fund_service" / "peer_group"
    single_file = pkg.with_suffix(".py")
    if pkg.exists() or single_file.exists():
        pytest.fail(
            "services/fund_service/peer_group 已创建：请将其加入 GUARDED_ROOTS "
            "（若为包）或确认 _py_files 的单文件分支已覆盖它（若为单文件模块），"
            "并删除本占位测试。"
        )
    pytest.skip(
        "services/fund_service/peer_group 尚未创建，计划于 Plan-3（M1.5）随 "
        "Peer Group 决策边界一起落地；在此之前 C-4 检查是 vacuous 的（可见占位，"
        "非静默通过）。"
    )
