# Benchmark 数据契约

> 文档版本：v1.0 | 日期：2026-09-08 | Owner：data-service

## 1. 边界

本域保存 Benchmark 定义、组成、基金映射和指数值。如何使用 Benchmark 计算 Alpha、Beta、
Information Ratio 与 Tracking Error 由 factor-service 定义。

## 2. 首版来源

Plan-2 使用版本化人工配置，不解析招募说明书。支持两个优先级：

1. 基金级人工配置；
2. 内部二级分类默认配置。

两者都不可得时返回 `BENCHMARK_UNAVAILABLE`，禁止临时替换。

## 3. 默认映射

| 内部分类 | Benchmark |
|---|---|
| `ACTIVE_EQUITY` | `CSI_300_TOTAL_RETURN` |
| `PASSIVE_EQUITY` | `CSI_300_TOTAL_RETURN` |
| `BOND` | `CHINA_BOND_COMPOSITE_FULL_PRICE` |
| `HYBRID` | `0.60 × CSI_300_TOTAL_RETURN + 0.40 × CHINA_BOND_COMPOSITE_FULL_PRICE` |

Passive Equity 应优先配置实际跟踪指数，默认映射仅作为已声明的分类兜底。

每个 Benchmark Index 必须记录 `index_type`。权益 Benchmark 使用 `TOTAL_RETURN`，债券 M1
使用 `FULL_PRICE`；`PRICE`、`TOTAL_RETURN` 与 `FULL_PRICE` 不得混用。指定类型不可得时返回
`BENCHMARK_UNAVAILABLE`，不得临时降级。

## 4. 时态字段

Benchmark Definition、Component 和 Mapping 均记录 `effective_at/valid_from`、
`available_at`、来源与版本。历史解析使用 `available_at <= decision_at` 的有效版本，基金转型
或映射修订不得改写历史。

## 5. 复合 Benchmark

组成权重以小数存储且和为 1。组合收益按同一交易日历对齐后加权；任一必需成分缺失时该日
复合收益 `UNAVAILABLE`，不得将剩余成分重归一。

## 6. Provider 映射

平台 Benchmark ID 与 Provider symbol 分离。上游代码变化通过版本化身份映射处理，不得把
Provider symbol 当作长期业务主键。

## 7. PIT 输出

查询结果至少返回 Benchmark ID、实际成分与权重、指数值版本、`available_at`、来源质量和
Mapping Version。该闭包必须能解释历史 REL Factor。