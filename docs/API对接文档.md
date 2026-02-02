# 抖音视频文本提取服务 - API 接口文档

> 版本：v1.0.0  
> 更新日期：2026-02-02  
> 文档作者：douyin_practice

---

## 一、文档概述

### 1.1 服务简介

本服务提供抖音视频文本提取功能，支持：
- 抖音链接解析（短链接、口令、完整链接）
- 视频元数据获取（标题、作者、时长等）
- 语音转文字（基于阿里云 DashScope）
- Markdown/Markdown 格式输出

### 1.2 服务地址

| 环境 | 地址 | 说明 |
|------|------|------|
| 本地 | `http://localhost:5000` | 本地开发环境 |
| 局域网 | `http://<你的IP>:5000` | 同局域网访问 |
| 外网 | `http://<公网IP>:5000` | 需要端口映射 |

### 1.3 接口列表

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 提取视频文本 | POST | `/api/extract` | 核心接口 |
| 获取配置 | GET | `/api/config` | 获取当前配置 |
| 保存配置 | POST | `/api/config` | 保存配置 |
| Web界面 | GET | `/` | Web操作界面 |

---

## 二、接口详情

### 2.1 提取视频文本

提取抖音视频中的语音文本内容。

#### 请求信息

- **URL**: `/api/extract`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| link | String | 是 | 抖音视频链接，支持以下格式：<br>- 短链接：`https://v.douyin.com/xxxxx/`<br>- 完整链接：`https://www.douyin.com/video/xxxxx`<br>- 分享口令：`8.32 nkV:/ 复制打开抖音...https://v.douyin.com/xxxxx/` |

#### 请求示例

```json
{
  "link": "https://v.douyin.com/iRNBho6U/"
}
```

#### 响应参数

| 字段 | 类型 | 说明 |
|------|------|------|
| success | Boolean | 是否成功 |
| metadata | Object | 视频元数据 |
| text | String | 提取的文本内容 |
| error | String | 错误信息（失败时返回） |

##### metadata 字段详情

| 字段 | 类型 | 说明 |
|------|------|------|
| video_id | String | 视频ID（19位数字） |
| title | String | 视频标题 |
| author | String | 作者昵称 |
| duration | Integer | 视频时长（秒） |
| video_url | String | 无水印视频地址 |
| cover_url | String | 视频封面地址 |
| douyin_url | String | 抖音分享链接 |

#### 成功响应示例

```json
{
  "success": true,
  "metadata": {
    "video_id": "7579925307658980654",
    "title": "齐刘海天团又添一位蛇喰梦子 #好剧推荐 #狂赌之渊",
    "author": "八点半movies",
    "duration": 214,
    "video_url": "https://www.douyin.com/aweme/v1/web/...",
    "cover_url": "https://p3.douyinpic.com/...",
    "douyin_url": "https://www.douyin.com/video/7579925307658980654"
  },
  "text": "在岛国有这么一所贵族学校，除了学费贵以外，还有一个传统就是赌博盛行。学习成绩好不好没关系，重要的是你有足够的筹码和精湛的赌术..."
}
```

#### 失败响应示例

```json
{
  "success": false,
  "error": "链接解析失败，请检查链接是否正确"
}
```

---

### 2.2 获取配置

获取当前服务配置信息（敏感信息会脱敏显示）。

#### 请求信息

- **URL**: `/api/config`
- **Method**: `GET`
- **Content-Type**: `application/json`

#### 响应示例

```json
{
  "success": true,
  "config": {
    "ASR_PROVIDER": "dashscope",
    "DASHSCOPE_API_KEY": "sk-xxxxx...",
    "MAX_VIDEO_DURATION": 600,
    "ASR_MODEL": "paraformer-v2",
    "OUTPUT_DIR": "./output",
    "OSS_ENABLE_FALLBACK": true,
    "OSS_ACCESS_KEY_ID": "LTAI5xxx...",
    "OSS_BUCKET_NAME": "your-bucket",
    "OSS_ENDPOINT": "oss-cn-wuhan-lr.aliyuncs.com"
  }
}
```

---

### 2.3 保存配置

修改服务配置。

#### 请求信息

- **URL**: `/api/config`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| DASHSCOPE_API_KEY | String | 条件 | 使用 DashScope 时必填 |
| ASR_PROVIDER | String | 否 | ASR 提供商：`dashscope` 或 `local` |
| MAX_VIDEO_DURATION | Integer | 否 | 最大视频时长（秒），默认 600 |
| ASR_MODEL | String | 否 | 识别模型，默认 `paraformer-v2` |
| OSS_ENABLE_FALLBACK | Boolean | 否 | 是否启用 OSS 兜底方案 |
| OSS_ACCESS_KEY_ID | String | 条件 | 启用 OSS 时必填 |
| OSS_ACCESS_KEY_SECRET | String | 条件 | 启用 OSS 时必填 |
| OSS_BUCKET_NAME | String | 条件 | 启用 OSS 时必填 |
| OSS_ENDPOINT | String | 条件 | 启用 OSS 时必填 |

#### 请求示例

```json
{
  "DASHSCOPE_API_KEY": "sk-your-api-key-here",
  "ASR_PROVIDER": "dashscope",
  "MAX_VIDEO_DURATION": 600
}
```

#### 响应示例

```json
{
  "success": true,
  "message": "配置保存成功"
}
```

---

## 三、错误码说明

| 错误码 | 错误信息 | 说明 |
|--------|----------|------|
| - | 请提供抖音链接 | 请求参数为空 |
| - | 链接解析失败，请检查链接是否正确 | 链接格式无效或已过期 |
| - | 视频信息获取失败，请检查链接是否有效 | 视频不存在或已删除 |
| - | 视频时长超过限制 | 视频超过最大时长限制 |
| - | 配置错误：未设置 DASHSCOPE_API_KEY | 需要配置 API Key |
| - | 语音识别失败，请检查 API Key 是否有效 | DashScope API 异常 |
| - | 处理失败: xxx | 其他运行时错误 |

---

## 四、调用示例

### 4.1 cURL 调用

```bash
# 提取视频文本
curl -X POST http://localhost:5000/api/extract \
  -H "Content-Type: application/json" \
  -d '{"link": "https://v.douyin.com/iRNBho6U/"}'

# 获取配置
curl http://localhost:5000/api/config
```

### 4.2 Java 调用示例（OkHttp）

```java
import okhttp3.*;
import org.json.JSONObject;

public class DouyinApiClient {
    
    private static final String BASE_URL = "http://localhost:5000";
    private final OkHttpClient client = new OkHttpClient();
    
    /**
     * 提取视频文本
     */
    public JSONObject extractVideo(String link) throws Exception {
        JSONObject requestBody = new JSONObject();
        requestBody.put("link", link);
        
        Request request = new Request.Builder()
                .url(BASE_URL + "/api/extract")
                .post(RequestBody.create(
                    requestBody.toString(),
                    MediaType.parse("application/json")
                ))
                .build();
        
        try (Response response = client.newCall(request).execute()) {
            String responseBody = response.body().string();
            return new JSONObject(responseBody);
        }
    }
    
    /**
     * 主函数测试
     */
    public static void main(String[] args) {
        try {
            DouyinApiClient client = new DouyinApiClient();
            JSONObject result = client.extractVideo("https://v.douyin.com/iRNBho6U/");
            
            if (result.getBoolean("success")) {
                JSONObject metadata = result.getJSONObject("metadata");
                String text = result.getString("text");
                
                System.out.println("视频标题: " + metadata.getString("title"));
                System.out.println("作者: " + metadata.getString("author"));
                System.out.println("时长: " + metadata.getInt("duration") + "秒");
                System.out.println("提取文本: " + text);
            } else {
                System.out.println("提取失败: " + result.getString("error"));
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

### 4.3 Java 调用示例（Spring Boot RestTemplate）

```java
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;

@Service
public class DouyinService {
    
    private final RestTemplate restTemplate;
    private final String serviceUrl = "http://localhost:5000";
    
    public DouyinService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }
    
    /**
     * 提取视频文本
     */
    public ExtractResponse extractVideo(String link) {
        // 构建请求体
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        
        String requestBody = String.format("{\"link\": \"%s\"}", link);
        HttpEntity<String> entity = new HttpEntity<>(requestBody, headers);
        
        // 发送请求
        ResponseEntity<ExtractResponse> response = restTemplate.postForEntity(
            serviceUrl + "/api/extract",
            entity,
            ExtractResponse.class
        );
        
        return response.getBody();
    }
    
    /**
     * 响应 DTO
     */
    @Data
    public static class ExtractResponse {
        private boolean success;
        private Metadata metadata;
        private String text;
        private String error;
        
        @Data
        public static class Metadata {
            private String videoId;
            private String title;
            private String author;
            private int duration;
            private String videoUrl;
            private String coverUrl;
            private String douyinUrl;
        }
    }
}

// 使用示例
@RestController
@RequestMapping("/api/douyin")
public class DouyinController {
    
    @Autowired
    private DouyinService douyinService;
    
    @PostMapping("/extract")
    public ResponseEntity<DouyinService.ExtractResponse> extract(
            @RequestBody Map<String, String> request) {
        String link = request.get("link");
        DouyinService.ExtractResponse result = douyinService.extractVideo(link);
        return ResponseEntity.ok(result);
    }
}
```

### 4.4 Python 调用示例

```python
import requests

class DouyinAPIClient:
    BASE_URL = "http://localhost:5000"
    
    def extract_video(self, link: str) -> dict:
        """提取视频文本"""
        response = requests.post(
            f"{self.BASE_URL}/api/extract",
            json={"link": link},
            headers={"Content-Type": "application/json"}
        )
        return response.json()

# 使用示例
client = DouyinAPIClient()
result = client.extract_video("https://v.douyin.com/iRNBho6U/")

if result["success"]:
    metadata = result["metadata"]
    text = result["text"]
    print(f"视频标题: {metadata['title']}")
    print(f"作者: {metadata['author']}")
    print(f"时长: {metadata['duration']}秒")
    print(f"提取文本: {text}")
else:
    print(f"提取失败: {result['error']}")
```

### 4.5 JavaScript/Node.js 调用示例

```javascript
/**
 * Node.js 调用示例（使用 axios）
 */
const axios = require('axios');

class DouyinAPIClient {
    constructor(baseUrl = 'http://localhost:5000') {
        this.baseUrl = baseUrl;
    }
    
    /**
     * 提取视频文本
     */
    async extractVideo(link) {
        try {
            const response = await axios.post(`${this.baseUrl}/api/extract`, {
                link: link
            }, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            return response.data;
        } catch (error) {
            if (error.response) {
                return error.response.data;
            }
            throw error;
        }
    }
}

// 使用示例
const client = new DouyinAPIClient();

async function main() {
    const result = await client.extractVideo('https://v.douyin.com/iRNBho6U/');
    
    if (result.success) {
        const { metadata, text } = result;
        console.log(`视频标题: ${metadata.title}`);
        console.log(`作者: ${metadata.author}`);
        console.log(`时长: ${metadata.duration}秒`);
        console.log(`提取文本: ${text}`);
    } else {
        console.log(`提取失败: ${result.error}`);
    }
}

main();
```

---

## 五、最佳实践

### 5.1 错误处理建议

```java
public class DouyinExtractor {
    
    public String extractWithRetry(String link, int maxRetry) {
        Exception lastException = null;
        
        for (int i = 0; i < maxRetry; i++) {
            try {
                JSONObject result = client.extractVideo(link);
                if (result.getBoolean("success")) {
                    return result.getString("text");
                } else {
                    // 如果是链接无效错误，不重试
                    String error = result.getString("error");
                    if (error.contains("链接解析失败") || 
                        error.contains("视频信息获取失败")) {
                        throw new IllegalArgumentException(error);
                    }
                }
            } catch (Exception e) {
                lastException = e;
            }
            
            // 等待后重试
            try {
                Thread.sleep(1000 * (i + 1));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        
        throw new RuntimeException("提取失败，已重试" + maxRetry + "次", lastException);
    }
}
```

### 5.2 超时配置建议

| 场景 | 推荐超时时间 |
|------|-------------|
| 短链接解析 | 10 秒 |
| 视频元数据获取 | 15 秒 |
| 语音转写（1分钟视频） | 30 秒 |
| 语音转写（5分钟视频） | 120 秒 |
| 整体请求 | 180 秒 |

### 5.3 并发控制建议

- **单用户请求频率**：建议每分钟不超过 10 次
- **并发请求数**：建议不超过 5 个并发连接
- **每日调用量**：根据阿里云 DashScope 配额自行调整

---

## 六、常见问题（FAQ）

### Q1: 链接解析失败

**原因**：链接可能已过期、被删除或格式不正确

**解决方案**：
1. 检查链接是否有效（抖音APP中能否正常打开）
2. 确认链接格式是否为以下之一：
   - `https://v.douyin.com/xxxxx/`
   - `https://www.douyin.com/video/xxxxx`
   - 包含上述链接的分享文本

### Q2: 语音识别失败

**原因**：DashScope API Key 无效、配额用完或网络问题

**解决方案**：
1. 检查 `.env` 中的 `DASHSCOPE_API_KEY` 是否正确
2. 登录阿里云控制台检查 DashScope 配额
3. 确认服务器网络可以访问 `dashscope.aliyuncs.com`

### Q3: 视频时长限制

**原因**：视频时长超过 `MAX_VIDEO_DURATION` 配置

**解决方案**：
在 `.env` 文件中调整 `MAX_VIDEO_DURATION` 值（单位：秒）

```ini
MAX_VIDEO_DURATION=600  # 默认 10 分钟
```

### Q4: 跨域访问

本服务已启用 CORS，允许跨域访问。如需更严格的跨域控制，可修改 `web_app.py`：

```python
# 允许特定域名访问
CORS(app, resources={r"/api/*": {"origins": "https://your-domain.com"}})

# 或禁用跨域
# 不启用 CORS
```

---

## 七、依赖说明

### 7.1 外部服务依赖

| 服务 | 用途 | 必需性 |
|------|------|--------|
| 阿里云 DashScope | 语音转文字 | 必需 |
| 阿里云 OSS | 兜底方案（可选） | 可选 |

### 7.2 网络要求

| 地址 | 用途 | 协议 |
|------|------|------|
| `v.douyin.com` | 抖音链接解析 | HTTPS |
| `www.douyin.com` | 视频信息获取 | HTTPS |
| `dashscope.aliyuncs.com` | 语音识别 API | HTTPS |

---

## 八、版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.0.0 | 2026-02-02 | 初始版本 |

---

## 九、联系方式

如有技术问题，请联系：

- **文档作者**：`douyin_practice`
- **项目地址**：`https://github.com/your-repo/douyin_practice`

---

> 本文档由 douyin_practice 项目生成
