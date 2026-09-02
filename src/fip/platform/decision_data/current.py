from typing import Any


class CurrentViewContext:
    """当前视图 —— 仅供 Live Portfolio 的实时状态展示使用（PIT-A4）。

    它与 PitDataContext 是【两个不相干的类型】，没有继承关系，也不暴露
    decision_at。这使二者在类型层面无法混用：需要历史视图的地方拿不到
    当前视图，反之亦然。历史数据的访问一律走 PitDataContext。
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    @property
    def session(self) -> Any:
        return self._session
