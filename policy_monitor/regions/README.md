# regions/ - Province/City Region Source Configurations

Each `.yaml` file defines policy data sources for one province, municipality, or autonomous region in China.

## Coverage (31 Regions)

### Municipalities (4)
| File | Region | Aliases | Sources |
|:-----|:-------|:--------|:-------:|
| beijing.yaml | Beijing | 北京, 京 | 2 |
| tianjin.yaml | Tianjin | 天津, 津 | 2 |
| shanghai.yaml | Shanghai | 上海, 沪 | 2 |
| chongqing.yaml | Chongqing | 重庆, 渝 | 2 |

### Provinces (22)
| File | Region | Aliases | Sources |
|:-----|:-------|:--------|:-------:|
| hebei.yaml | Hebei | 河北, 冀 | 2 |
| shanxi.yaml | Shanxi | 山西, 晋 | 2 |
| liaoning.yaml | Liaoning | 辽宁, 辽 | 2 |
| jilin.yaml | Jilin | 吉林, 吉 | 2 |
| heilongjiang.yaml | Heilongjiang | 黑龙江, 黑 | 2 |
| jiangsu.yaml | Jiangsu | 江苏, 苏 | 2 |
| anhui.yaml | Anhui | 安徽, 皖 | 2 |
| fujian.yaml | Fujian | 福建, 闽 | 2 |
| jiangxi.yaml | Jiangxi | 江西, 赣 | 2 |
| shandong.yaml | Shandong | 山东, 鲁 | 2 |
| henan.yaml | Henan | 河南, 豫 | 2 |
| hunan.yaml | Hunan | 湖南, 湘 | 2 |
| sichuan.yaml | Sichuan | 四川, 川, 蜀 | 2 |
| guizhou.yaml | Guizhou | 贵州, 黔 | 2 |
| yunnan.yaml | Yunnan | 云南, 滇 | 2 |
| shaanxi.yaml | Shaanxi | 陕西, 陕, 秦 | 2 |
| gansu.yaml | Gansu | 甘肃, 甘, 陇 | 2 |
| qinghai.yaml | Qinghai | 青海, 青 | 2 |
| hubei.yaml | Hubei | 湖北, 鄂 | 6 |
| zhejiang.yaml | Zhejiang | 浙江, 浙 | 5 |
| guangdong.yaml | Guangdong | 广东, 粤 | 5 |
| hainan.yaml | Hainan | 海南, 琼 | 5 |

### Autonomous Regions (4)
| File | Region | Aliases | Sources |
|:-----|:-------|:--------|:-------:|
| neimenggu.yaml | Inner Mongolia | 内蒙古, 蒙 | 2 |
| guangxi.yaml | Guangxi | 广西, 桂 | 2 |
| ningxia.yaml | Ningxia | 宁夏, 宁 | 2 |
| xinjiang.yaml | Xinjiang | 新疆, 新 | 2 |

### City-Level (1)
| File | Region | Parent | Sources |
|:-----|:-------|:-------|:-------:|
| enshi.yaml | Enshi Prefecture | Hubei | 3 (+6 from Hubei) |

## How to Use

```bash
# List all regions
python -m policy_monitor.main list-regions

# Crawl national + specific province
python -m policy_monitor.main run --region Beijing
python -m policy_monitor.main run --region 四川
python -m policy_monitor.main run --region guangdong

# City level (automatically chains to parent province)
python -m policy_monitor.main run --region Enshi
# = national sources + Hubei province sources + Enshi sources
```

## How to Add a New Region

1. Create a new YAML file: `{pinyin}.yaml` (e.g., `hubei.yaml`)
2. Fill in the template below
3. Run `python main.py list-regions` to verify

## Template

```yaml
name: Province Full Name
aliases: ["Chinese short name", "abbreviation", "pinyin"]
parent_province: null  # Set to parent province name for cities

sources:
  - name: "StateCouncil-ProvinceName"
    url: "https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary_gwyzcwjk&q=ProvinceName&..."
    type: api
    frequency: weekly
    enabled: true
    note: "State Council API filtered by province name"

  - name: "Province Government Portal"
    url: "https://www.example.gov.cn/zcwj/"
    type: html
    frequency: weekly
    selectors:
      list: ".list_content li a"
    enabled: true
```

## Aliases

The system supports multiple alias formats for each region:
- Chinese full name: 北京市
- Chinese short name: 北京
- Chinese abbreviation: 京
- English pinyin: beijing

All are case-insensitive. Use any format with `--region`.
