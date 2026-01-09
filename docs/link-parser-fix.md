# 抖音链接解析器修复记录

## 问题描述

### 问题现象

在使用 Web 界面提取抖音视频文本时，遇到链接解析失败的错误：

```
🔍 开始解析链接...
✓ 提取到链接: https://v.douyin.com/PkQJMi
✓ 重定向成功
❌ 无法从 URL 中提取视频 ID
```

**错误链接示例：**
```
6.97 06/12 SLw:/ p@D.uS 不上班 你至少还有12种赚钱方法（上) # 赚钱 # 商业思维 # 不上班 # 个人成长 # 林熊猫认知  https://v.douyin.com/PkQJMi_Sb00/ 复制此链接，打开Dou音搜索，直接观看视频！
```

### 错误信息

- HTTP 状态码：400
- 错误提示：`链接解析失败，请检查链接是否正确`
- 发生时间：2026-01-09

---

## 问题原因分析

### 1. 短链接格式变化

**原因：**
抖音的短链接格式发生了变化，新的短链接格式支持下划线字符，例如：
- 旧格式：`https://v.douyin.com/PkQJMi/`
- 新格式：`https://v.douyin.com/PkQJMi_Sb00/`

**原始代码问题：**
```python
# 原始正则表达式不支持下划线
SHARE_TEXT_PATTERN = r'(https?://v\.douyin\.com/[A-Za-z0-9]+)'
```

这个正则表达式只匹配字母和数字，不支持下划线，导致无法正确提取包含下划线的短链接。

### 2. 重定向 URL 格式变化

**原因：**
抖音短链接重定向后的 URL 可能不包含传统的 `/video/` 路径格式，导致无法直接从 URL 中提取视频 ID。

**原始代码问题：**
```python
def extract_video_id(self, url: str) -> Optional[str]:
    # 只尝试从 URL 路径中提取
    match = re.search(self.VIDEO_ID_PATTERN, url)  # 只匹配 /video/数字
    if match:
        return match.group(1)
    return None  # 无法提取就返回 None
```

原始代码只支持以下格式：
- `https://www.douyin.com/video/123456789`
- `https://www.douyin.com/modal/detail/123456789`

但实际重定向后的 URL 可能：
- 不包含 `/video/` 路径
- 可能重定向到分享页面（`/share/video/`）
- 可能重定向到其他格式的页面

### 3. 缺少备用提取方案

**原因：**
原始代码只从 URL 中提取视频 ID，没有从页面 HTML 内容中提取的备用方案。当无法从 URL 提取时，应该尝试从页面 HTML 中解析视频 ID。

**原始代码限制：**
- 只尝试从 URL 提取
- 没有获取页面 HTML 内容
- 没有从 `window._ROUTER_DATA` 中提取视频 ID 的逻辑

---

## 解决方案

### 1. 更新短链接正则表达式

**修复：**
```python
# 更新正则表达式，支持下划线
SHARE_TEXT_PATTERN = r'(https?://v\.douyin\.com/[A-Za-z0-9_]+)'
```

**效果：**
- 可以正确提取包含下划线的短链接
- 支持新旧两种格式

### 2. 增强视频 ID 提取方法

**修复：**
实现了多层提取策略：

```python
def extract_video_id_from_url(self, url: str) -> Optional[str]:
    """从 URL 中提取视频 ID（支持多种格式）"""
    patterns = [
        r'/video/(\d+)',                      # /video/123456789
        r'/modal/detail/(\d+)',               # /modal/detail/123456789
        r'(?:/video/|video/|/share/video/)(\d+)',  # 通用匹配
        r'video_id["\']?\s*[:=]\s*["\']?(\d+)',    # JSON 中的 video_id
        r'aweme_id["\']?\s*[:=]\s*["\']?(\d+)',    # JSON 中的 aweme_id
    ]
    # 依次尝试每种模式
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
```

**效果：**
- 支持更多 URL 格式
- 可以从 URL 参数中提取视频 ID

### 3. 从 HTML 页面提取视频 ID

**修复：**
实现了 `extract_video_id_from_html()` 方法，参考 `fetcher.py` 的实现方式：

```python
def extract_video_id_from_html(self, html: str) -> Optional[str]:
    """从 HTML 页面中提取视频 ID"""
    # 方法1: 从 window._ROUTER_DATA 提取
    pattern = re.compile(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", re.DOTALL)
    match = pattern.search(html)
    if match:
        json_data = json.loads(match.group(1).strip())
        loader_data = json_data.get("loaderData", {})
        
        # 处理视频和图文两种类型
        VIDEO_ID_PAGE_KEY = "video_(id)/page"
        NOTE_ID_PAGE_KEY = "note_(id)/page"
        
        # 从 loaderData 中提取视频信息
        if VIDEO_ID_PAGE_KEY in loader_data:
            video_info_res = loader_data[VIDEO_ID_PAGE_KEY].get("videoInfoRes", {})
            item_list = video_info_res.get("item_list", [])
            if item_list:
                aweme_id = item_list[0].get("aweme_id") or item_list[0].get("item_id")
                return str(aweme_id)
    
    # 方法2: 从 meta 标签提取
    # 方法3: 从页面中直接搜索数字 ID
    ...
```

**效果：**
- 可以从页面 HTML 中提取视频 ID
- 支持多种提取方法作为备用方案

### 4. 多重备用方案

**修复：**
改进了 `parse()` 方法，实现多重备用策略：

```python
def parse(self, link_text: str) -> Optional[str]:
    # 1. 提取短链接（支持下划线）
    short_url = self.extract_short_url(link_text)
    
    # 2. 重定向并获取 HTML 内容
    if 'v.douyin.com' in short_url:
        full_url, html_content = self.resolve_redirect(short_url)
    else:
        full_url = short_url
        html_content = None
    
    # 3. 首先尝试从 URL 中提取视频 ID
    video_id = self.extract_video_id_from_url(full_url)
    
    # 4. 如果无法从 URL 提取，尝试从 HTML 中提取
    if not video_id and html_content:
        video_id = self.extract_video_id_from_html(html_content)
    
    # 5. 如果还是没有，尝试直接请求页面
    if not video_id:
        response = self.session.get(full_url, timeout=self.timeout)
        video_id = self.extract_video_id_from_html(response.text)
    
    return video_id
```

**效果：**
- 多层备用方案，提高解析成功率
- 即使 URL 格式发生变化，也能从页面内容中提取

---

## 技术细节

### 修改文件

- `douyin_practice_web/src/parser.py`

### 主要变更

1. **正则表达式更新**
   - `SHARE_TEXT_PATTERN`: 添加下划线支持
   - 新增 `VIDEO_ID_IN_URL_PATTERN`: 支持更多 URL 格式

2. **新增方法**
   - `extract_video_id_from_url()`: 增强的 URL 提取方法
   - `extract_video_id_from_html()`: 从 HTML 提取视频 ID 的方法

3. **方法改进**
   - `resolve_redirect()`: 现在返回 URL 和 HTML 内容
   - `parse()`: 实现多重备用提取策略

4. **依赖更新**
   - 导入 `json` 模块用于解析 `window._ROUTER_DATA`
   - 导入 `Tuple` 类型提示

### 兼容性

- ✅ 兼容旧格式的短链接
- ✅ 兼容新格式的短链接（包含下划线）
- ✅ 兼容直接包含 `/video/` 的完整 URL
- ✅ 兼容各种重定向后的 URL 格式

---

## 测试验证

### 测试用例

1. **旧格式短链接**
   ```
   https://v.douyin.com/iRNBho6U/
   ```

2. **新格式短链接（包含下划线）**
   ```
   https://v.douyin.com/PkQJMi_Sb00/
   ```

3. **完整分享文本**
   ```
   6.97 06/12 SLw:/ p@D.uS 不上班 你至少还有12种赚钱方法（上) # 赚钱 # 商业思维 # 不上班 # 个人成长 # 林熊猫认知  https://v.douyin.com/PkQJMi_Sb00/ 复制此链接，打开Dou音搜索，直接观看视频！
   ```

4. **完整 URL**
   ```
   https://www.douyin.com/video/7445285776618482979
   ```

### 预期结果

所有测试用例应该能够成功解析并提取视频 ID。

---

## 经验总结

### 1. 平台格式变化应对

- **问题**：第三方平台（如抖音）的链接格式可能随时变化
- **经验**：正则表达式应该尽量宽泛，避免过于严格的匹配规则
- **建议**：定期测试和更新解析规则，保持对平台变化的适应性

### 2. 多层备用策略

- **问题**：单一提取方法容易因格式变化而失败
- **经验**：实现多层备用提取策略，提高成功率
- **建议**：
  1. 首先尝试简单的方法（从 URL 提取）
  2. 如果失败，尝试复杂的方法（从 HTML 提取）
  3. 最后尝试直接请求页面

### 3. 参考现有实现

- **问题**：重新实现可能导致不一致
- **经验**：参考项目中已有的成功实现（如 `fetcher.py`）
- **建议**：保持代码一致性，复用已验证的逻辑

### 4. 错误处理

- **问题**：错误信息不够详细
- **经验**：添加详细的错误日志，方便排查问题
- **建议**：在关键步骤添加日志输出，便于调试

---

## 后续改进建议

1. **单元测试**
   - 为解析器添加单元测试
   - 测试各种链接格式和边界情况
   - 确保格式变化时能及时发现问题

2. **监控和告警**
   - 监控链接解析成功率
   - 当解析失败率超过阈值时发送告警
   - 定期检查是否需要更新解析规则

3. **文档更新**
   - 维护支持的链接格式列表
   - 记录已知的不兼容格式
   - 提供用户友好的错误提示

4. **性能优化**
   - 缓存重定向结果
   - 避免重复请求相同的链接
   - 优化 HTML 解析性能

---

## 相关文件

- `douyin_practice_web/src/parser.py` - 链接解析器实现
- `douyin_practice_web/src/fetcher.py` - 视频信息获取器（参考实现）
- `douyin_practice_web/web_app.py` - Web 应用主文件

---

## 更新记录

- **2026-01-09**: 修复短链接解析失败问题，支持下划线格式和多重提取策略
- **作者**: AI Assistant
- **版本**: v0.2.1

---

## 参考资料

1. [douyin-mcp-server](https://github.com/yzfly/douyin-mcp-server) - 抖音 MCP 服务器实现参考
2. 项目内部文档：`douyin_practice_web/src/fetcher.py` - HTML 解析实现参考
