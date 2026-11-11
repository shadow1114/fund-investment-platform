"""Add benchmark request metadata and seed benchmark indexes.

Revision ID: 0044
Revises: 0043
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

_BENCHMARK_SEED_JSON = r"""[
  {
    "provider_code": "000906",
    "display_name": "中证800",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930930",
    "display_name": "中证港股通综合",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11001",
    "display_name": "中证全债",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11009",
    "display_name": "中证综合债",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931078",
    "display_name": "中证转债及可交换债",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000510",
    "display_name": "中证A500",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000905",
    "display_name": "中证500",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000933",
    "display_name": "中证医药卫生",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000922",
    "display_name": "中证红利",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000942",
    "display_name": "中证内地消费",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000985",
    "display_name": "中证全指",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000852",
    "display_name": "中证1000",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930950",
    "display_name": "中证偏股型基金",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30355",
    "display_name": "中证800成长",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930599",
    "display_name": "中证高端装备制造",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399808",
    "display_name": "中证新能源",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931059",
    "display_name": "中证同业存单AAA",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930609",
    "display_name": "中证纯债债券型基金",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000998",
    "display_name": "中证TMT",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000964",
    "display_name": "中证新兴产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11023",
    "display_name": "中证债券型基金",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30356",
    "display_name": "中证800价值",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930965",
    "display_name": "中证港股通医药C",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30357",
    "display_name": "中证800相对成长",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931582",
    "display_name": "中证数字经济",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930050",
    "display_name": "中证A50",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931573",
    "display_name": "中证港股通科技",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930997",
    "display_name": "中证新能源汽车",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000907",
    "display_name": "中证700",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000977",
    "display_name": "中证内地低碳",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930914",
    "display_name": "中证港股通高股息",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931643",
    "display_name": "中证科创创业50",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399975",
    "display_name": "中证全指证券公司",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930820",
    "display_name": "中证高端制造",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931151",
    "display_name": "中证光伏产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000944",
    "display_name": "中证内地资源",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30184",
    "display_name": "中证全指半导体产品与设备",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931454",
    "display_name": "中证港股通消费",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30597",
    "display_name": "中证新材料主题",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931303",
    "display_name": "中证国债",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000903",
    "display_name": "中证A100",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000991",
    "display_name": "中证全指医药卫生",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30590",
    "display_name": "中证机器人",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000827",
    "display_name": "中证环保",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930955",
    "display_name": "中证红利低波动100",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930740",
    "display_name": "沪深300红利低波动",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30007",
    "display_name": "中证芯片产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931027",
    "display_name": "中证港股通大消费",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11021",
    "display_name": "中证股票型基金",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399986",
    "display_name": "中证银行",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930713",
    "display_name": "中证人工智能主题",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932365",
    "display_name": "中证全指自由现金流",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399967",
    "display_name": "中证军工",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931187",
    "display_name": "中证科技100",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000932",
    "display_name": "中证消费",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930850",
    "display_name": "中证智能制造",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931719",
    "display_name": "中证电池主题",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000955",
    "display_name": "中证国有企业综合",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30535",
    "display_name": "中证互联网",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000990",
    "display_name": "中证全指消费",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399989",
    "display_name": "中证医疗",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932000",
    "display_name": "中证2000",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30344",
    "display_name": "中证健康产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11015",
    "display_name": "中证短债",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399974",
    "display_name": "中证国有企业改革",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930962",
    "display_name": "中证港股通工业综合",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932357",
    "display_name": "中证专精特新100",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930851",
    "display_name": "中证云计算",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000989",
    "display_name": "中证全指可选消费",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931355",
    "display_name": "中证周期100",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000824",
    "display_name": "中证国有企业红利",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399814",
    "display_name": "中证大农业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930653",
    "display_name": "中证食品饮料",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30351",
    "display_name": "中证500成长",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932368",
    "display_name": "中证800自由现金流",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000993",
    "display_name": "中证全指信息技术",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931743",
    "display_name": "中证半导体材料设备主题",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30009",
    "display_name": "中证商品期货成份",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931752",
    "display_name": "中证工程机械主题",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30074",
    "display_name": "中证服务业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931238",
    "display_name": "中证沪深港黄金产业股票",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000806",
    "display_name": "中证消费服务",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000813",
    "display_name": "中证细分化工产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930986",
    "display_name": "中证金融科技",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399971",
    "display_name": "中证传媒",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30202",
    "display_name": "中证软件指数",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931162",
    "display_name": "中证可转债及可交换债券50",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000832",
    "display_name": "中证转债",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399970",
    "display_name": "中证移动互联网",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11100",
    "display_name": "中证香港100",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30199",
    "display_name": "中证全指电力指数",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931230",
    "display_name": "中证汽车零部件",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932497",
    "display_name": "中证500价值",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931755",
    "display_name": "中证SSE碳中和",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931247",
    "display_name": "中证信创",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30217",
    "display_name": "中证全指医疗器械",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000978",
    "display_name": "中证医药100",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931865",
    "display_name": "中证半导体产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000931",
    "display_name": "中证可选消费",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930610",
    "display_name": "中证普通债券型基金",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931892",
    "display_name": "中证有色金属矿业主题",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932456",
    "display_name": "中证科创创业AI",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930601",
    "display_name": "中证软件",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000949",
    "display_name": "中证农业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931494",
    "display_name": "中证消费电子",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931026",
    "display_name": "中证港股通TMT",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11054",
    "display_name": "中证装备产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931167",
    "display_name": "中证先进制造100",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000995",
    "display_name": "中证全指公用事业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000987",
    "display_name": "中证全指原材料",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932075",
    "display_name": "中证全指金融",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399812",
    "display_name": "中证养老产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931152",
    "display_name": "中证创新药产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932004",
    "display_name": "中证国新央企综合",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000861",
    "display_name": "中证央企创新",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11059",
    "display_name": "中证工业有色金属",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930616",
    "display_name": "中证文体",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930771",
    "display_name": "中证新能源产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931583",
    "display_name": "中证沪港深数字经济",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11146",
    "display_name": "中证港股通内地金融",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930632",
    "display_name": "中证稀有金属",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H11153",
    "display_name": "中证香港内地国有企业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930697",
    "display_name": "中证全指家用电器",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931160",
    "display_name": "中证全指通信设备",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930708",
    "display_name": "中证有色金属",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399998",
    "display_name": "中证煤炭",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930726",
    "display_name": "中证生物医药",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000811",
    "display_name": "中证细分有色金属产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930939",
    "display_name": "中证500质量成长",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931848",
    "display_name": "中证800红利低波动",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30086",
    "display_name": "中证800金融",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932047",
    "display_name": "中证REITs全收益",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931786",
    "display_name": "中证中信债股优选稳健",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000926",
    "display_name": "中证中央企业综合",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000962",
    "display_name": "中证中游制造产业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931139",
    "display_name": "中证CS消费50",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931775",
    "display_name": "中证全指房地产",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30171",
    "display_name": "中证全指运输",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930901",
    "display_name": "中证动漫游戏",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399973",
    "display_name": "中证国防",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "930915",
    "display_name": "中证港股通综合(人民币)",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000935",
    "display_name": "中证信息",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399997",
    "display_name": "中证白酒",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000933",
    "display_name": "中证医药",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000300",
    "display_name": "沪深300",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000919",
    "display_name": "沪深300价值",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931859",
    "display_name": "沪深300碳中和",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932366",
    "display_name": "沪深300自由现金流",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000914",
    "display_name": "沪深300金融地产",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000821",
    "display_name": "沪深300红利",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "932431",
    "display_name": "沪深300质量",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000969",
    "display_name": "沪深300非周期行业",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000913",
    "display_name": "沪深300医药卫生",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "399983",
    "display_name": "沪深300地产等权重",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30124",
    "display_name": "沪深300安中动态策略",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "931375",
    "display_name": "沪深300质量成长低波动",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000957",
    "display_name": "沪深300运输",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "H30035",
    "display_name": "沪深300非银行金融",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "000984",
    "display_name": "沪深300等权重",
    "source": "csindex",
    "api": null,
    "param": null
  },
  {
    "provider_code": "HSI",
    "display_name": "恒生",
    "source": "akshare",
    "api": "stock_hk_index_daily_em",
    "param": null
  },
  {
    "provider_code": "HSCI",
    "display_name": "恒生综合",
    "source": "akshare",
    "api": "stock_hk_index_daily_em",
    "param": null
  },
  {
    "provider_code": "HSTECH",
    "display_name": "恒生科技",
    "source": "akshare",
    "api": "stock_hk_index_daily_em",
    "param": null
  },
  {
    "provider_code": "HSHCI",
    "display_name": "恒生医疗保健",
    "source": "akshare",
    "api": "stock_hk_index_daily_em",
    "param": null
  },
  {
    "provider_code": "HSCICG",
    "display_name": "恒生消费",
    "source": "akshare",
    "api": "stock_hk_index_daily_em",
    "param": null
  },
  {
    "provider_code": "HSSCHK",
    "display_name": "恒生港股通",
    "source": "akshare",
    "api": "stock_hk_index_daily_em",
    "param": null
  },
  {
    "provider_code": "HSHKBIO",
    "display_name": "恒生生物科技",
    "source": "akshare",
    "api": "stock_hk_index_daily_em",
    "param": null
  },
  {
    "provider_code": "2c90818811afed8d0111c0c672b31578",
    "display_name": "中债综合全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "2c90818811afed8d0111c0c672b31578",
    "display_name": "中债综合财富(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "2c90818811afed8d0111c0c672b31578",
    "display_name": "中债综合财富(1-3年)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "02",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "2c90818811afed8d0111c0c672b31578",
    "display_name": "中债综合全价(1-3年)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "02",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "2c9081e50e8767dc010e879387370009",
    "display_name": "中债总全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "8a8b2ca0332abed20134ea76d8885831",
    "display_name": "中债新综合财富(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "2c90818811afed8d0111c0c672b31578",
    "display_name": "中债综合财富(1年以下)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "01",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "2c9081e50e8767dc010e879387370009",
    "display_name": "中债总全价(1-3年)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "02",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "8a8b2ca0332abed20134ea76d8885831",
    "display_name": "中债新综合财富(1-3年)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "02",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "2c9081e50e8767dc010e879387370009",
    "display_name": "中债总财富(1-3年)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "02",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "8a8b2ca0332abed20134ea76d8885831",
    "display_name": "中债新综合全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "8a8b2ca0332abed20134ea76d8885831",
    "display_name": "中债新综合全价(1-3年)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "02",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "2c90818811afed8d0111c0c672b31578",
    "display_name": "中债综合全价(1年以下)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "01",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "d05cf50d9388ff213bd02a7cd7da7f1a",
    "display_name": "中债-1-5年债券综合财富(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "19",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "7e5d649217bd9cd7749cdcfd144dfcfb",
    "display_name": "中债-0-3年债券综合全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "15",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "8a8b2ca038d716f10138dadde8416adc",
    "display_name": "中债-信用债总全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "2c9081e50e8767dc010e879387370009",
    "display_name": "中债总财富(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "8a8b2c83638ecdf001638ffed9ae0007",
    "display_name": "中债-1-3年国开行债券",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "02",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "7e5d649217bd9cd7749cdcfd144dfcfb",
    "display_name": "中债-0-3年债券综合财富(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "15",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "d05cf50d9388ff213bd02a7cd7da7f1a",
    "display_name": "中债-1-5年债券综合全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "19",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "85e9dc831c7335636e8f540bf6c63f41",
    "display_name": "中债-0-3年政策性金融债",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "15",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "dd5dc21b4a5bd48abcf34c949e50b817",
    "display_name": "中债-0-5年债券综合财富(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "16",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "8a8b2c8f5a62e9ca015a645fe3b60001",
    "display_name": "中债-国债及政策性银行债全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "2c90818811afed8d0111c0c672b31578",
    "display_name": "中债综合财富(3-5年)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "03",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "8a8b2c8f5a62e9ca015a645fe3b60001",
    "display_name": "中债国债及政策性银行债全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "8a8b2c8f5a62e9ca015a645fe3b60001",
    "display_name": "中债国债及政策性银行债财富(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "CFZS"
    }
  },
  {
    "provider_code": "8a8b2ca0332abed20134ea76d8885831",
    "display_name": "中债新综合全价(1年以下)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "01",
      "index_type": "QJZS"
    }
  },
  {
    "provider_code": "2c9081e50e8767dc010e87a9d5650060",
    "display_name": "中债-金融债券总全价(总值)",
    "source": "chinabond",
    "api": null,
    "param": {
      "period_type": "00",
      "index_type": "QJZS"
    }
  }
]"""


def upgrade() -> None:
    op.add_column(
        "benchmark_index", sa.Column("source", sa.String(64), nullable=True), schema="market"
    )
    op.add_column("benchmark_index", sa.Column("api", sa.Text(), nullable=True), schema="market")
    op.add_column(
        "benchmark_index",
        sa.Column("param", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="market",
    )
    op.alter_column(
        "benchmark_index",
        "provider_symbol",
        existing_type=sa.String(128),
        nullable=True,
        schema="market",
    )
    op.alter_column(
        "benchmark_index", "currency", existing_type=sa.String(8), nullable=True, schema="market"
    )
    op.alter_column(
        "benchmark_index", "index_type", existing_type=sa.String(32), nullable=True, schema="market"
    )
    op.execute(
        sa.text("""
        WITH seed AS (
            SELECT
                item->>'provider_code' AS provider_code,
                item->>'display_name' AS display_name,
                item->>'source' AS source,
                NULLIF(item->>'api', '') AS api,
                CASE
                    WHEN item->'param' IS NULL OR item->'param' = 'null'::jsonb THEN NULL
                    ELSE item->'param'
                END AS param
            FROM jsonb_array_elements(CAST(:seed_json AS jsonb)) AS seed_data(item)
        )
        INSERT INTO market.benchmark_index (provider_code, display_name, source, api, param)
        SELECT seed.provider_code, seed.display_name, seed.source, seed.api, seed.param
        FROM seed
        WHERE NOT EXISTS (
            SELECT 1 FROM market.benchmark_index AS existing
            WHERE existing.display_name = seed.display_name
        )
    """).bindparams(seed_json=_BENCHMARK_SEED_JSON)
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE market.benchmark_index
        SET provider_symbol = COALESCE(provider_symbol, 'UNASSIGNED-' || id::text),
            currency = COALESCE(currency, 'CNY'),
            index_type = COALESCE(index_type, 'FULL_PRICE')
        WHERE provider_symbol IS NULL OR currency IS NULL OR index_type IS NULL
    """
    )
    op.alter_column(
        "benchmark_index",
        "index_type",
        existing_type=sa.String(32),
        nullable=False,
        schema="market",
    )
    op.alter_column(
        "benchmark_index", "currency", existing_type=sa.String(8), nullable=False, schema="market"
    )
    op.alter_column(
        "benchmark_index",
        "provider_symbol",
        existing_type=sa.String(128),
        nullable=False,
        schema="market",
    )
    op.drop_column("benchmark_index", "param", schema="market")
    op.drop_column("benchmark_index", "api", schema="market")
    op.drop_column("benchmark_index", "source", schema="market")
