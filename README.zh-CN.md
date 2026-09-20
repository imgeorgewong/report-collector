# report-collector

[English](README.md) | **中文**

一个小型的、注册表驱动的 Python 框架，用于把公开发布的报告（经济展望、市场报告、调查）按月归档，并用一份 manifest 记录每一期应发报告的状态。

它是为"不好惹的源"设计的：PDF 藏在文章页后面、URL 原地覆盖、重定向落到无关页面、列表只保留滚动窗口、以及只能手工下载的刊物。

> 状态：进行中。

## 它做什么

- **每个源是一份声明，不是一段代码**：落地页、链接模式、发布节奏、允许的 host。
- **按发布月份归档**，不是按下载日期。
- **manifest** 每期一行：`downloaded`、`unchanged`、`manual`、`manual-done`、`missed`、`no-issue`、`future`、`absent`。
- **防假阳性**：重定向到别处的页面、同一次运行内的重复内容、站外链接、原地过期的常青 URL、错误的版次。
- **手工源是一等公民**：不能或不该自动化的，记成待办行；手工下载的文件放进对应月份文件夹会被自动认领。
- **健康检查**：连跑两次，第二次 `downloaded` 必须为 0。
- **默认守规矩**：遵守 `robots.txt`、限速、始终开启 TLS 验证。

## 它不做什么

不用于绕过登录、付费墙、表单或其他访问控制。需要这些的源一律记成手工行。下载到的报告版权归各出版方所有，不会进入本仓库。

## 安装

```
git clone https://github.com/imgeorgewong/report-collector.git
cd report-collector
git config core.hooksPath .githooks
```

需要 Python 3.10 以上。没有任何依赖要装。

## 使用

```
python -m report_collector check --registry examples/registry_example.py
python -m report_collector run   --registry examples/registry_example.py --archive ./archive --year 2026
python -m report_collector run   --registry examples/registry_example.py --archive ./archive --year 2026
python -m report_collector audit --archive ./archive
```

第二次 `run` 不是笔误，那是验收测试：必须报 `downloaded=0`。不是 0 就说明去重键匹配到了每次都会变的东西，这个采集器以后每个月都会把同样的报告重下一遍。

归档结构：

```
archive/
  _manifest.csv
  2026/
    01_Jan/ acme__2026-01__Monthly-Outlook.pdf
    02_Feb/ ...
```

## 声明一个源

```python
from report_collector import Cadence, Source, Tier

Source(
    key="acme",                       # 短标识，同时用作文件名前缀
    name="Monthly Outlook",
    publisher="Acme Institute",
    tier=Tier.SCRAPE,                 # TEMPLATE | SCRAPE | MANUAL
    cadence=Cadence.MONTHLY,          # MONTHLY | QUARTERLY | ANNUAL | WINDOW
    landing_url="https://acme.example/reports",
    allowed_hosts=("acme.example",),  # 默认拒绝，SCRAPE 必填
    extensions=(".pdf",),
    edition_tokens=("{year}",),       # 防止常青 URL 一直发去年那版
    year_window=1,                    # 落地页上的链接最多往回取几年
)
```

`check` 不发任何请求就能校验注册表，声明写错了会在跑之前就说出来。

## 状态

| 状态 | 含义 |
|---|---|
| `downloaded` | 这一轮新下载的 |
| `unchanged` | 已归档，内容一致 |
| `manual` | 要人去下，原因写在行里 |
| `manual-done` | 在月份文件夹里找到了手工下载的文件 |
| `missed` | 该发了、找过了、已经拿不到 |
| `no-issue` | 出版方这一期没发 |
| `future` | 还没到 |
| `absent` | 该发但什么都没匹配上：没发、滚出列表了，或者正则不对 |

`manual` 和 `missed` 故意分开：前者是人还能补的活，后者是归档里的一个洞。

## 测试

```
python -m unittest discover -s tests
```

47 个测试，全部离线：引擎接收一个 fetcher 对象，测试传的是返回固定响应的假 fetcher。只有网络行为（robots、限速、重试）不在覆盖范围内。

## 相关仓库

[public-data-powerquery](https://github.com/imgeorgewong/public-data-powerquery) —— 取公开官方经济数据的 Excel Power Query 连接器。

## 作者

Jingbo Wang（[@imgeorgewong](https://github.com/imgeorgewong)）· [imgeorgewong.github.io](https://imgeorgewong.github.io)

## 许可

MIT，见 `LICENSE`。
