# AMC 8 智学助手

AI 驱动的 AMC 8 数学竞赛辅导工具 (MVP)。

## 功能
- 📝 PDF / 图片 / 文字三种输入方式
- 🎭 AI 三段式讲题（数学小剧场 / 教练透视眼 / 逻辑拆解步）
- 💡 脚手架式逐步提示
- 📐 GeoGebra 交互式几何图（点拖拽 + 辅助线动画）
- 🎤 孩子讲思路 + AI 苏格拉底式追问
- 🔊 云希男声朗读

## 配额系统

新用户每日免费 50,000 tokens（约 5-8 道题完整体验），用完后可填入自己的 Gemini API Key 继续无限使用。

## 部署 (Streamlit Cloud)

### 1. Streamlit Secrets 配置

在 `Settings → Secrets` 中添加：

```toml
GEMINI_API_KEY = "您的平台 Gemini API Key（提供给免费用户使用）"
ADMIN_PASSWORD = "您的管理员密码"
```

### 2. 文件结构

```
.
├── app.py                  # 主程序
├── geometry_engine.py      # 几何 JSON → GeoGebra 引擎
├── quota.py                # 配额系统
├── requirements.txt        # 依赖
└── usage.json              # 自动生成的使用记录（可丢失）
```

### 3. 管理后台

侧边栏 → 🔐 管理员 → 输入密码即可进入：

- 今日总调用 / Tokens / 成本 / 熔断状态
- 用户消耗排行榜
- 7 天趋势
- 手动熔断 / 重置 / 清空

## 配额规则

| 项目 | 数值 |
|---|---|
| 单用户每日 tokens | 50,000 |
| 全站每日 tokens | 4,000,000 |
| 成本熔断阈值 | $1.00 |
| 重置时间 | UTC 0:00 |
| 用户填自己 Key | 完全绕开配额 |

## 技术栈

- Streamlit + Python
- Gemini 2.5 Flash (多模态)
- GeoGebra (交互几何)
- Edge-TTS (云希男声)
- streamlit-cookies-controller (用户识别)
