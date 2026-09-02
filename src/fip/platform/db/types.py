from sqlalchemy import Numeric

# 存储精度（spec §5.4.3）。金融数值禁止使用浮点。
AmountNumeric = Numeric(20, 4)   # 金额
NavNumeric = Numeric(18, 8)      # 净值 / 因子值
RatioNumeric = Numeric(12, 8)    # 权重 / 比率 / 利率
