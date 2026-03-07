# 🎙️ Paper Morning - 学术晨间播报

每天早上自动为你生成一期学术新闻音频播报，用 5 分钟了解最值得关注的 AI 论文动态。

**戴上耳机，刷牙洗脸的时候听。**

## 工作原理

```
HuggingFace Daily Papers ─┐
                           ├→ 关键词打分排序 → LLM 生成中文播报稿 → edge-tts 语音合成 → RSS Feed
arXiv API ────────────────┘
```

每天凌晨 6:30 (UTC+8)，GitHub Actions 自动运行:

1. 从 HuggingFace Trending Papers + arXiv 抓取最新论文
2. 按你配置的关键词计算相关性，选出 Top 5
3. 调用 LLM (DeepSeek/MiniMax/Claude) 生成中文新闻播报稿
4. 用 edge-tts 合成为 MP3 音频 (成熟知性女声)
5. 生成 Podcast RSS Feed，推送到 GitHub Pages

你可以用任何播客客户端订阅这个 Feed。

## 快速开始

### 1. Fork 这个仓库

### 2. 配置 API Key

在你 fork 的 repo 中，进入 `Settings > Secrets and variables > Actions`，添加:

| Secret 名称 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API key (如果用 DeepSeek) |
| `MINIMAX_API_KEY` | MiniMax API key (如果用 MiniMax) |
| `ANTHROPIC_API_KEY` | Anthropic API key (如果用 Claude) |

只需配置你选择的那个 LLM 的 key。

### 3. 修改配置

编辑 `config.yaml`:

- `sources.arxiv.keywords`: 改成你关注的研究方向关键词
- `content.host_context`: 描述你的研究背景，让 LLM 生成更贴合你的解读
- `llm.provider`: 选择 `deepseek` / `minimax` / `claude`
- `tts.voice`: 选择喜欢的语音 (见下方列表)
- `publish.site_url`: 改成你的 GitHub Pages URL

### 4. 启用 GitHub Pages

进入 repo 的 `Settings > Pages`，Source 选择 `Deploy from a branch`，Branch 选 `main`，文件夹选 `/docs`。

### 5. 手动触发测试

进入 `Actions` 标签页，选择 `Daily Paper Morning`，点击 `Run workflow` 手动触发一次。

### 6. 订阅播客

音频生成后，用播客客户端 (苹果播客/小宇宙/Pocket Casts) 订阅:

```
https://你的用户名.github.io/paper-morning/feed.xml
```

## 可选语音

| Voice ID | 风格 |
|---|---|
| `zh-CN-XiaoruiNeural` | 成熟知性女声 (默认) |
| `zh-CN-XiaoyiNeural` | 温暖自然女声 |
| `zh-CN-XiaoxiaoNeural` | 活泼通用女声 |
| `zh-CN-YunxiNeural` | 阳光男声 |
| `zh-CN-YunyangNeural` | 新闻联播男声 |

完整列表: `pip install edge-tts && edge-tts --list-voices | grep zh-CN`

## 本地运行

```bash
git clone https://github.com/你的用户名/paper-morning.git
cd paper-morning
pip install -r requirements.txt
export DEEPSEEK_API_KEY="your-key-here"
python src/main.py
```

生成的文件在 `docs/` 目录下。

## 项目结构

```
paper-morning/
├── .github/workflows/
│   └── daily-cast.yml      # GitHub Actions 定时任务
├── src/
│   ├── main.py              # 主流程
│   ├── fetcher.py           # 论文抓取 & 排序
│   ├── scriptwriter.py      # LLM 生成播报稿
│   ├── synthesizer.py       # edge-tts 语音合成
│   └── feed_generator.py    # RSS Feed & 网页生成
├── docs/                    # 静态站点 (GitHub Pages)
│   ├── index.html
│   ├── feed.xml
│   └── episodes/            # 每日音频 & 文稿
├── config.yaml              # 用户配置
├── requirements.txt
└── README.md
```

## 自定义

### 添加更多数据源

在 `src/fetcher.py` 中添加新的 `fetch_xxx()` 函数，然后在 `fetch_and_rank()` 中调用即可。

### 修改播报风格

编辑 `src/scriptwriter.py` 中的 `_build_prompt()` 函数，调整 prompt 模板。

### 双人对话模式

如果后续想升级为 NotebookLM 风格的双人播客，可以:
1. 修改 prompt 让 LLM 输出带角色标记的对话稿
2. 用两个不同的 edge-tts voice 分别合成
3. 用 pydub 拼接音频

## License

MIT

## Acknowledgments

- 论文数据来自 [arXiv](https://arxiv.org) 和 [HuggingFace Daily Papers](https://huggingface.co/papers)
- 语音合成由 [edge-tts](https://github.com/rany2/edge-tts) 提供
- Thank you to arXiv for use of its open access interoperability.
