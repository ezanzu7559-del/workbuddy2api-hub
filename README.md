# 把 workbuddy2api-hub + DeepSeek 反代 部署到 Render（免费）

让 DeepSeek 伪装的 API 挂在公网上，**不开电脑也能用**。基于官方网关镜像 + 追加 DeepSeek 模型名反代，云端体验和本地完全一致（`deepseek-chat` / `deepseek-reasoner`）。

## 本目录文件

| 文件 | 作用 |
| --- | --- |
| `Dockerfile` | 基于官方镜像 `ghcr.io/ardeyouxipianyi/workbuddy2api-hub:latest`，追加反代 |
| `start.sh` | 同时启动网关（内部 8788）+ DeepSeek 反代（对外 PORT） |
| `deepseek-gateway.py` | DeepSeek 模型名改写反代（`deepseek-chat`→`deepseek-v4.1-flash` 等） |
| `render.yaml` | Render Blueprint 一键部署配置 |

## 部署步骤（约 5 分钟）

### 1. 建 GitHub 仓库
把这 4 个文件 push 到一个**新仓库**（可以私有）。不需要包含网关源码，官方镜像已带。

```bash
# 在 render-deploy 目录里
git init
git add .
git commit -m "deploy workbuddy2api-hub deepseek facade to render"
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 2. Render 用 Blueprint 部署
1. 注册 [render.com](https://render.com)（**免费，不需要信用卡**，用 GitHub 登录）。
2. Dashboard → **New +** → **Blueprint** → 选你刚 push 的仓库。
3. 部署时它让你填 **API_KEY**（必填，`sync: false` 的变量会要求手动填）——填一个强随机串，例如 `sk-你的自定义强密钥`。
4. 顺手把 `PANEL_PASSWORD` 也改成强密码（默认 `change-me-to-a-strong-password`）。
5. 点 **Apply**，等它构建部署（几分钟）。

### 3. 记下你的云端地址
部署完成后，得到类似 `https://workbuddy-deepseek-api.onrender.com` 的地址。

### 4. 导入账号（重要）
Render 免费层**重新部署会丢数据**，所以部署后要把账号重新导一次。用本地那个账号文件：

```bash
python add-account.py --gateway https://你的应用.onrender.com \
  --password 你设的面板密码 \
  --file "C:\Users\Administrator\Downloads\codebuddy-accounts-3-1791699088769 (1).txt"
```

> 每重新部署一次，都要重跑这条命令重新导账号。

### 5. 客户端配置

```
Base URL : https://你的应用.onrender.com/v1
API Key  : 你第 2 步填的 API_KEY
模型      : deepseek-chat / deepseek-reasoner
```

## 注意事项（务必看）

1. **15 分钟休眠**：免费层无请求 15 分钟后休眠，下次请求要等 30~60 秒唤醒。第一次请求慢是正常的，不是挂了。
2. **数据不持久**：免费层不能挂持久磁盘，**重新部署/重建容器后账号会清空**，重跑第 4 步导入即可。日常休眠/唤醒不会丢。
3. **必须设 API_KEY**：公网暴露，不设 key 等于把额度白送人。`start.sh` 里没设 `API_KEY` 会直接拒绝启动。
4. **安全风险**：账号 token 明文存在第三方服务器上，且可能违反 WorkBuddy 服务条款有封号风险。介意的话建议用自建 VPS。
5. **免费额度**：Render 免费 750 实例小时/月，单实例够用。

## 想固定模型映射

改 `deepseek-gateway.py` 顶部的 `MODEL_MAP` 后重新 push，Render 会自动重新部署（记得重导账号）。
