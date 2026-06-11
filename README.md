# GitHub Trending Daily Push

每天中午 12 点自动获取 GitHub 当日热门开源项目，并通过飞书机器人推送。

## 使用方式

1. 在飞书群里添加「自定义机器人」，复制 Webhook 地址。
2. 新建一个 GitHub 仓库，把本项目文件推上去。
3. 在仓库里添加 Actions Secret：
   - `FEISHU_WEBHOOK_URL`：飞书机器人的 Webhook 地址
4. GitHub Actions 会在北京时间每天 12:00 自动运行。

也可以在 Actions 页面手动运行 `Daily GitHub Trending Push` workflow 测试。

## 本地测试

只打印消息，不推送：

```bash
DRY_RUN=true python main.py
```

Windows PowerShell：

```powershell
$env:DRY_RUN="true"; python main.py
```

实际推送：

```powershell
$env:FEISHU_WEBHOOK_URL="你的飞书 webhook"; python main.py
```

## 配置项

- `FEISHU_WEBHOOK_URL`：必填，飞书机器人 Webhook。
- `TRENDING_LIMIT`：可选，默认 `10`。
- `TRENDING_API_URL`：可选。如果你有稳定的 Trending API，可以填这个地址；不填时直接读取 GitHub Trending。
- `GITHUB_TRENDING_URL`：可选，默认 `https://github.com/trending?since=daily`。
- `DRY_RUN`：可选，设置为 `true` 时只打印消息。
