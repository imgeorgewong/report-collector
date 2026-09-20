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

## 开发

每个克隆都需要启用一次敏感内容检查：

```
git config core.hooksPath .githooks
```

此后每次提交都会运行 `tools/check_sensitive.py`，它会拦下 Office 和数据文件、内部 URL 与路径、GUID，以及看起来像凭据的字符串。

仓库公开之前，再跑一次全量扫描：

```
python3 tools/check_sensitive.py --all
```

## 相关仓库

[public-data-powerquery](https://github.com/imgeorgewong/public-data-powerquery) —— 取公开官方经济数据的 Excel Power Query 连接器。

## 作者

Jingbo Wang（[@imgeorgewong](https://github.com/imgeorgewong)）· [imgeorgewong.github.io](https://imgeorgewong.github.io)

## 许可

MIT，见 `LICENSE`。
