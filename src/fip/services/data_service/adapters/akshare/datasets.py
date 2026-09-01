"""AKShare 数据集契约声明。

本文件的列名与函数名已对照已安装的 AKShare 1.18.94 版本核对（探查脚本
见 task-10-report.md）。若升级 AKShare 后契约测试失败，回到探查步骤
重新核对，不要凭猜测修改。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    code: str
    callable_name: str
    fixed_params: dict[str, str] = field(default_factory=dict)
    required_columns: frozenset[str] = frozenset()


DATASETS: dict[str, DatasetSpec] = {
    "fund_list": DatasetSpec(
        code="fund_list",
        callable_name="fund_name_em",
        required_columns=frozenset({"基金代码", "基金简称", "基金类型"}),
    ),
    "fund_nav": DatasetSpec(
        code="fund_nav",
        callable_name="fund_open_fund_info_em",
        fixed_params={"indicator": "单位净值走势"},
        required_columns=frozenset({"净值日期", "单位净值"}),
    ),
    "fund_cumulative_nav": DatasetSpec(
        code="fund_cumulative_nav",
        callable_name="fund_open_fund_info_em",
        fixed_params={"indicator": "累计净值走势"},
        required_columns=frozenset({"净值日期", "累计净值"}),
    ),
    "fund_distribution": DatasetSpec(
        code="fund_distribution",
        callable_name="fund_open_fund_info_em",
        fixed_params={"indicator": "分红送配详情"},
        # 探查结果：AKShare 1.18.94 实际列为「每10份分红」，非本文件此前
        # 猜测的「每份分红」——以探查结果为准（见 task-10-report.md）。
        required_columns=frozenset({"年份", "权益登记日", "除息日", "每10份分红"}),
    ),
    "fund_split": DatasetSpec(
        code="fund_split",
        callable_name="fund_open_fund_info_em",
        fixed_params={"indicator": "拆分详情"},
        required_columns=frozenset({"年份", "拆分折算日", "拆分折算比例"}),
    ),
    "risk_free_rate": DatasetSpec(
        code="risk_free_rate",
        callable_name="bond_china_yield",
        required_columns=frozenset({"曲线名称", "日期"}),
    ),
}
