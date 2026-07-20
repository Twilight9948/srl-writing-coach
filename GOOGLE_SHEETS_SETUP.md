# Google Sheets 配置（免费，替代 Supabase）

## 1. 创建 Google 表格

1. 打开 https://sheets.google.com → 新建表格
2. 命名：`SRL Writing Research Data`
3. 复制表格 ID（URL 里 `/d/` 和 `/edit` 之间的字符串）

## 2. 创建 Service Account

1. 打开 https://console.cloud.google.com
2. 新建项目 → APIs & Services → Enable **Google Sheets API**
3. Credentials → Create Credentials → **Service Account**
4. 创建后 → Keys → Add Key → JSON → 下载 JSON 文件

## 3. 共享表格

把 JSON 文件里的 `client_email`（类似 `xxx@xxx.iam.gserviceaccount.com`）  
复制到 Google 表格 → **共享** → 给这个邮箱 **编辑者** 权限

## 4. Streamlit Cloud Secrets

Streamlit Cloud → 你的 App → **Settings → Secrets**，粘贴：

```toml
DEEPSEEK_API_KEY = "你的deepseek密钥"

GOOGLE_SHEET_ID = "你的表格ID"

RESEARCH_PASSWORD = "srl2026"

[google_sheets_credentials]
type = "service_account"
project_id = "从JSON复制"
private_key_id = "从JSON复制"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "从JSON复制"
client_id = "从JSON复制"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "从JSON复制"
```

保存后 App 会自动重启。

## 5. 查看研究数据

打开 Google 表格即可：

- 按 `student_id`（邮箱）筛选 → 某个学生的全部记录
- 按 `test_round` → Session 1 / 2 / 3
- `conversation` 列 → 对话 JSON

可 **文件 → 下载 → Excel** 做统计分析。

## 研究者查看数据（App 内置后台）

在 Streamlit 链接后面加 `?research=1`，例如：

```
https://你的app.streamlit.app/?research=1
```

默认密码：`srl2026`（在 Secrets 里设置 `RESEARCH_PASSWORD` 可修改）

也可以直接打开 Google 表格查看原始数据。


App 仍正常运行，数据保存在服务器本地 `srl_writing_data/` 文件夹。  
配置 Sheets 后，每次对话会自动同步到表格。
