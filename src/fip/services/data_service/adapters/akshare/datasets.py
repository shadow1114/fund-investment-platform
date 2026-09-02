"""AKShare 数据集契约声明。

本文件的列名与函数名已对照已安装的 AKShare 1.18.94 版本核对（探查脚本
见 task-10-report.md）。若升级 AKShare 后契约测试失败，回到探查步骤
重新核对，不要凭猜测修改。
"""

from dataclasses import dataclass, field

# `bond_china_yield` 的期限列。探查结果（AKShare 1.18.94，见 task-10-report.md）：
# 实际列为 [曲线名称, 日期, 3月, 6月, 1年, 3年, 5年, 7年, 10年, 30年] —— 8 个期限列，
# 【没有】「2年」。
#
# 这 8 列必须进 required_columns：它们是 parse_yield_curve_frame 真正读取的列。
# 契约此前只声明 {曲线名称, 日期}，于是上游把「1年」改成「1Y」时，解析器会静默
# 返回零行（宽表展开找不到任何期限列），而契约测试照样绿 —— 缺列是上游 schema
# 漂移最常见的形状，恰恰必须由契约来接。
#
# parse.TENOR_LABELS 里还认得「2年」：认得但不要求。上游目前不给这一列，
# 把它写进契约会让契约测试对着一列上游从未提供的东西报错。二者的一致性由
# tests/unit/test_yield_curve_parsing.py 的漂移测试守住。
YIELD_TENOR_COLUMNS: frozenset[str] = frozenset(
    {"3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"}
)


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
        # 「曲线名称」不是可选的装饰：同一个日期下有三条不同的曲线（国债 /
        # 中短期票据AAA / 商业银行普通债AAA），缺了它就无法回答「这是哪条
        # 曲线」，而 RiskFreeRate 的主键第一列正是 curve_code。
        required_columns=frozenset({"曲线名称", "日期"}) | YIELD_TENOR_COLUMNS,
    ),
}
