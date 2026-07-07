# 开源发布安全检查清单

上传公开仓库前，请确认以下项均已处理。

## 1. 密钥与凭证

- [ ] 代码与文档中 **无真实 API Key**（仅使用 `您的API_Key` 等占位符）
- [ ] 未提交 `.env` 文件（已在 `.gitignore`）
- [ ] 未在 README / Issue 中粘贴 SSH 密码或云实例密码

## 2. 部署地址

- [ ] `uni-app/config.js` 未提交（使用 `config.example.js` 模板）
- [ ] 未提交 `uni-app/unpackage/` 构建产物
- [ ] 文档中无个人云实例 URL、实例 ID、内网 IP

## 3. 发布前扫描命令

```bash
# 搜索疑似 API Key
rg -i "sk-[a-zA-Z0-9._-]{10,}" --glob "!uni-app/unpackage/**"

# 搜索云实例域名
rg "seetacloud|autodl-container" .

# 搜索内网 IP
rg "172\.16\.\d+\.\d+" .
```

期望：无真实密钥；无个人部署地址。

## 4. 推荐仓库结构

```text
├── server/                 # FastAPI 推理服务
├── uni-app/
│   ├── config.example.js   # 提交
│   └── config.js           # 本地，gitignore
├── docs/
│   ├── PROJECT_IMPLEMENTATION.md
│   └── GITHUB_PUBLISH_CHECKLIST.md
└── evaluation/ + training/
```

## 5. 运维提醒

- 云 GPU 实例不用时关机
- API Key 定期轮换
- 公网服务建议增加鉴权（当前 MVP 无鉴权）
