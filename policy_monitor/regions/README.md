# regions/ - Province/City Region Source Configurations

Each `.yaml` file in this directory defines policy data sources for one province or city.

## How to Add a New Province

1. Create a new YAML file named `{province_name}.yaml` (e.g., `四川省.yaml`)
2. Fill in the template below
3. Run `python main.py list-regions` to verify

## Template

```yaml
name: 省份全称
aliases: ["简称", "别称", "pinyin"]
parent_province: null  # Set to parent province name for cities (e.g., "湖北省")

sources:
  - name: "省政府名称"
    url: "https://www.example.gov.cn/zcwj/"
    type: html
    frequency: daily
    selectors:
      list: ".list li a, .news-list li a"
    enabled: true
```

## Fields

| Field | Required | Description |
|:------|:--------:|:------------|
| `name` | Yes | Canonical name (used as ID) |
| `aliases` | Yes | List of alternative names users might type |
| `parent_province` | No | For cities: the parent province name. Auto-includes parent sources. |
| `sources[]` | Yes | List of policy data sources for this region |
| `sources[].name` | Yes | Display name of the source |
| `sources[].url` | Yes | Entry URL to fetch |
| `sources[].type` | Yes | Parser type: `html`, `api`, `rss`, `sitemap` |
| `sources[].selectors.list` | For HTML | CSS selector for policy list links |
| `sources[].enabled` | No | Default: true |

## Tips

- Test each URL manually first: open in browser, check if it loads without JS
- Use browser DevTools to find CSS selectors for the policy list
- If a site blocks scraping, set `enabled: false` and add a comment
- For cities, always set `parent_province` so provincial sources are included automatically
