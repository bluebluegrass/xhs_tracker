# 小红书追踪器 (Xiahongshu Tracker)

一个轻量、自动的小红-shu关键词追踪机器人。

它借助 GitHub Actions 的强大能力，定时抓取小红-shu上你关心的关键词的最新笔记，并第一时间推送到你的 Telegram。从此，再也不会错过任何重要动态！

## 📬 推送内容包含什么？

- 笔记标题、作者、摘要（自动精简到 220 字以内）
- 发布时间（UTC）
- 原文链接，以及在手机端点击后可直接跳转小红-shu App 的温馨提示
- 当次运行没有新内容时，会推送“暂无更新”的提醒

## ✨ 懒人福音：一键订阅

不想自己动手？没问题！我已经为你准备好了一个公开频道。

**请注意：** 这个频道目前**专注于日本户外活动**，主要追踪以下关键词组合的最新笔记：

-   日本 爬山 摇人
-   日本 爬山 招募
-   日本 爬山 搭子
-   日本 露营 摇人
-   日本 露营 搭子
-   日本 户外 摇人
-   日本 户外 搭子

**如果你对以上内容感兴趣，欢迎点击下方链接直接订阅：**

**[👉 点我订阅 @xhs_tracker 👈](https://t.me/xhs_tracker)**

---

## 🚀 动手达人：搭建你自己的追踪器

如果你想追踪个性化的关键词（例如其他地区、其他兴趣），或者想拥有一个完全属于自己的频道，欢迎 Fork 本项目！整个过程大约需要 10-15 分钟。

### 准备工作

在开始之前，请确保你拥有：
1.  一个 GitHub 账号
2.  一个 Telegram 账号
3.  一个能正常登录小红-shu网页版的浏览器（推荐 Chrome 或 Firefox）

### 部署步骤

**第 1 步：Fork 本项目**
- 点击本页面右上角的 **Fork** 按钮，将此仓库复制到你自己的 GitHub 账号下。

**第 2 步：创建 Telegram 机器人和频道**
1.  在 Telegram 中搜索并打开 **[@BotFather](https://t.me/BotFather)**。
2.  发送 `/newbot` 指令，按照提示创建一个新的机器人。创建成功后，@BotFather 会给你一串 **机器人 Token**，请务必复制并保存好（形如 `123456:ABC-DEF123456...`）。
3.  创建一个新的 Telegram **频道（Channel）** 或 **群组（Group）**。
4.  将刚刚创建的机器人添加为该频道/群组的**管理员**。
5.  搜索并打开 **[@userinfobot](https://t.me/userinfobot)**，它会返回你的个人信息，其中的 `chat_id` 就是你频道的 ID。
    - **注意**：对于频道，请先在频道里发一条消息，然后**转发**这条消息给 @userinfobot，它返回的 `Forwarded from channel` 部分会包含频道的 `chat_id`（通常以 `-100` 开头）。

**第 3 步：配置仓库的 Secrets**
- 回到你 Fork 的 GitHub 仓库页面，点击 `Settings` -> `Secrets and variables` -> `Actions`。
- 点击 `New repository secret`，依次添加以下 **5 个** 变量：

| Secret 名称    | 含义                                 | 示例                                                               |
| :------------- | :----------------------------------- | :----------------------------------------------------------------- |
| `KEYWORDS`     | 你想追踪的关键词，用**换行**或**逗号**分隔 | `AI绘画` <br> `AIGC最新资讯`                                      |
| `TG_BOT_TOKEN` | 你的 Telegram 机器人 Token             | `123456:ABC-DEF123456...`                                          |
| `TG_CHAT_ID`   | 接收消息的频道/群组 ID               | `-1001234567890`                                                   |
| `XHS_COOKIE`   | 小红-shu网页版 Cookie（获取方法见下文）  | `a1=...; web_session=...;`                                         |
| `USER_AGENT`   | 浏览器 User-Agent （获取方法见下文） | `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...`              |

**第 4 步：启用并运行 Actions**
1.  在你的仓库页面，点击 `Actions` 选项卡。
2.  如果看到一个 "I understand my workflows, go ahead and enable them" 的按钮，请点击它以启用。
3.  在左侧选择 `Run XHS Watcher` 工作流。
4.  点击右侧的 `Run workflow` 按钮，手动触发一次。
5.  稍等片刻，如果一切顺利，你的 Telegram 频道应该会收到第一条推送（可能是“暂无更新”的提示）。

至此，你的个人小红-shu追踪器已搭建完成！它将默认每小时自动运行一次。

### 关键配置获取方法：`XHS_COOKIE` & `USER_AGENT`

> **重要提示**：Cookie 会过期！如果机器人停止工作并提示 400 错误，通常意味着你需要重新获取 Cookie。

1.  在你的电脑浏览器上，打开一个**新的无痕窗口**，并访问 [www.xiaohong-shu.com](https://www.xiaohong-shu.com/) 完成登录。
2.  登录后，按 `F12` 或 `右键 -> 检查` 打开**开发者工具**，切换到 **Network (网络)** 面板。
3.  随便进行一次搜索，例如搜索 "旅行"。
4.  在 Network 面板的请求列表中，找到一个以 `notes` 结尾的请求（URL 类似 `.../api/sns/web/v1/search/notes`）。
5.  点击这个请求，在右侧的 **Request Headers (请求标头)** 中：
    -   找到 `Cookie:`，复制它后面的**完整**字符串，这就是 `XHS_COOKIE`。
    -   找到 `User-Agent:`，复制它后面的完整字符串，这就是 `USER_AGENT`。

## ⚙️ 工作原理

- **定时触发**：通过 `.github/workflows/xhs.yml` 文件中的 Cron 表达式配置，默认每小时自动运行一次。
- **环境准备**：在 GitHub Actions 虚拟环境中安装 Python 3.11、项目依赖库以及 Playwright 无头浏览器。
- **执行抓取**：运行核心脚本 `xhs_watch.py`，它会读取你配置的关键词，模拟浏览器请求小红-shu搜索接口。
- **内容推送**：脚本会筛选出 14 天内发布的新笔记，并格式化成美观的消息（包含封面、标题、作者和链接）发送到你的 Telegram。
- **防止重复**：利用 Actions Artifact 功能，将已推送过的笔记 ID 保存在 `xhs_seen.json` 文件中，确保每次只推送新内容。

## 🛠️ 本地运行与自定义

如果你想在本地进行测试或二次开发，可以按以下步骤操作：

1.  **环境设置**
    ```bash
    # 创建并激活虚拟环境
    python -m venv .venv
    source .venv/bin/activate  # Windows 用户请使用: .venv\Scripts\activate
    
    # 安装依赖
    pip install -r requirements.txt
    ```

2.  **配置环境变量并运行**
    ```bash
    # Linux / macOS
    export KEYWORDS="关键词1, 关键词2"
    export TG_BOT_TOKEN="你的Token"
    export TG_CHAT_ID="你的ChatID"
    export XHS_COOKIE="你的Cookie"
    export USER_AGENT="你的User-Agent"
    
    # 运行脚本
    python xhs_watch.py
    ```
    > Windows 用户请使用 `set` 命令设置环境变量，例如 `set KEYWORDS="关键词1, 关键词2"`。

### 自定义建议

- **调整频率**：编辑 `.github/workflows/xhs.yml` 中的 `cron` 表达式，可以修改自动运行的频率。
- **消息格式**：在 `xhs_watch.py` 中修改 `build_post_message` 函数，可以定制你自己的 Telegram 消息排版。
- **筛选逻辑**：直接在 `xhs_watch.py` 中添加更复杂的过滤条件，比如按作者、点赞数等筛选。
- **笔记时效**：修改 `MAX_POST_AGE` 变量的值（默认为 14），可以扩大或缩小推送笔记的时间范围。

---
希望这个工具能为你带来便利！
