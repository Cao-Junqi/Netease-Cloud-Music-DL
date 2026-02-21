```markdown
# NetEase Car Music Downloader (网易云车机音乐自动化下载工具)

基于 Python 编写的网易云音乐全自动化批量下载工作流 (Workflow)。专为车载信息娱乐系统 (Car Infotainment System) 打造，支持全量获取 VIP 权限内的 320k 高品质流媒体，并强制绑定同名歌词文件与完整的 ID3 元数据 (Metadata)。

## 核心特性 (Core Features)

* **全链路自动化**：输入 Playlist ID 即可实现 `歌单全量解析 -> 鉴权劫持 -> MP3 流媒体抓取 -> LRC 歌词生成 -> ID3 标签写入` 的一键闭环。
* **底层会话接管 (Session Hijacking)**：通过全局挂载 `MUSIC_U` 等鉴权凭证，突破未登录状态下 API 的 10 首截断限制，合法拉取 320kbps 音频直链。
* **车机级强兼容 (Car OS Compatibility)**：
  * **物理级同名**：强一致性生成完全同名的 `.mp3` 与 `.lrc`，确保车机挂载 (File Mount) 时精准匹配。
  * **元数据硬编码**：引入 `mutagen` 库，向音频流底层硬编码写入专辑封面图 (APIC)、歌手名 (TPE1)、专辑名 (TALB) 与标题 (TIT2)，兼容 ID3v2.3 规范。
  * **特殊字符清洗**：自动剔除底层文件系统 (File System) 不支持的非法字符，防止拷贝至 U 盘或车机读取时发生文件截断。
* **防风控与脏数据隔离**：内置流媒体体积校验逻辑，自动拦截并抛弃因权限不足导致的 44s 试听片段 (Free Trial)。

---

## 环境与依赖 (Dependencies)

项目运行依赖 Python 3.8+ 环境，并在终端执行以下命令挂载第三方模块：

```bash
python -m pip install requests pyncm mutagen -i [https://pypi.tuna.tsinghua.edu.cn/simple](https://pypi.tuna.tsinghua.edu.cn/simple)

```

| 依赖库 (Library) | 核心作用 (Purpose) |
| --- | --- |
| `requests` | 处理图片下载及基础的音频流式写入 (Stream Write)。 |
| `pyncm` | 网易云逆向 API 框架，负责复杂加密算法的脱壳与鉴权上下文 (Authentication Context) 维护。 |
| `mutagen` | 底层音频元数据处理，负责向落地的 MP3 容器中嵌入封面和 ID3 标签。 |

---

## 快速部署 (Quick Start)

### 1. 获取鉴权凭证 (Cookie)

1. 在浏览器无痕模式下登录网易云音乐 Web 端 (`music.163.com`)。
2. 按 `F12` 打开开发者工具 (Developer Tools)，刷新页面。
3. 在 **Network (网络)** 面板中抓取任意官方域名的请求头，完整复制 `Cookie` 字段的值（必须包含 `MUSIC_U` 与 `__csrf`）。

### 2. 核心配置修改

使用编辑器打开主程序脚本 `vip_car_music_dl.py`，修改底部入口的常量配置：

```python
if __name__ == "__main__":
    # 1. 注入你抓取到的完整 Cookie 字符串
    VIP_COOKIE = "MUSIC_U=你的凭证; __csrf=你的凭证;"
    
    # 2. 定义本地落地的全局物理路径
    target_dir = r"D:\music"
    
    # 3. 定义需要全量下发的歌单 ID 数组 (支持多个)
    target_playlists = [
        "8055396278", 
        "12644048660"
    ]

```

### 3. 执行工作流

```bash
python vip_car_music_dl.py

```

---

## 边界情况与兜底方案 (Edge Cases & Fallbacks)

在执行大规模批量下载时，脚本已针对以下边界情况做了防御性设计：

* **44s 试听风控 (Trial Block)**：当账号处于非 VIP 状态或 Cookie 失效时，服务端会重定向吐出 44s 的试听媒体流。脚本内嵌了 **`Content-Length < 1.5MB`** 的强制校验阈值，命中后自动跳过，拒绝污染本地数据。
* **数字专辑/强 DRM 拦截**：针对需要额外按张付费的数字专辑（如周杰伦全集）或无版权下架歌曲，`GetTrackAudio` 接口将直接拒绝返回 URL，终端会抛出 `[!] 音频直链被拒绝` 警告并平滑处理下一个轨道，不会引发进程死锁 (Deadlock)。
* **防熔断休眠 (Rate Limiting)**：每次轨道处理后强制 `time.sleep(1.5)`，规避高频并发触发的 WAF 封禁 (HTTP 429 Too Many Requests)。

---

## 许可证 (License)

[MIT License](https://www.google.com/search?q=LICENSE)
