# 扮演project
欢迎来到 扮演project 仓库！这个机器人允许用户与各种人格互动，设置时区，管理聊天记录等。它还具有问候调度功能，保持对话的活跃性。

### 建议云部署，教程进群自取

---

### QQ讨论群：797631364，有问题可以在群里问

---

## 功能

- **动态人格**：选择不同的人格以增强聊天体验。
- **记忆管理**：机器人可以记住之前的互动，并使用这些信息提供相关的回应。
- **时区设置**：设置您的时区以接收及时的问候和消息。
- **重试机制**：如果需要，可以重试最后的回应。
- **主动问候**：根据用户的活动和时区，机器人会生成发送问候消息。
- **定时提醒**：用户可以设定提醒事项和时间，机器人会在对应时间提醒用户。

## 命令

好的，我会根据您的新命令更新使用指南部分。以下是更新后的内容：

---

## 命令

### 启动机器人
```
/start
```
开始。

### 设置时区
```
/time <时区>
```
设置您的时区（例如 `Asia/Shanghai`），每次重启都需要发送。主动搭话功能和定时提醒功能必须设置时区，前者不设置会导致时间紊乱，后者不设置无法启动。

### 使用特定人格
```
/use <人格>
```
切换到指定的人格，获得更有趣的对话体验。

### 重试最后的回应
```
/retry
```
重新获取机器人的最后回应。

### 清除聊天记录
```
/clear
```
清除当前的聊天记录。

### 列出和管理记忆（请慎重使用此功能，因为它会消耗大量API）
```
/list
```
列出所有存储的记忆。

```
/list <数字>
```
删除某条记忆。

```
/list <数字> <记忆内容>
```
添加或升级/覆盖某条记忆。

### 提醒事项
```
/clock <时间> <提醒事件>
```
设定一次性提醒事项和提醒时间。

```
/clockeveryday <时间> <提醒事件>
```
设定每日定时提醒事项和提醒时间。

```
/clocklist
```
查看提醒列表。

```
/clockclear <编号>
```
删除某条一次性提醒。

```
/clockclearevery <编号>
```
删除某条每日提醒。

---

希望这些更新能帮助您更好地管理和使用机器人！如果有任何进一步的修改需求，请随时告诉我。

## 安装

1. **克隆仓库**
   ```bash
   git clone https://github.com/AileenAugustus/RPproject-AtelegramChatBOT.git
   cd RPproject-AtelegramChatBOT

   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置**
   在根目录找到 `config.py` 文件，填入相应内容：
   ```python
   API_KEY = 'your_openai_api_key'
   TELEGRAM_BOT_TOKEN = 'your_telegram_bot_token'
   ALLOWED_USER_IDS = []  # 替换为允许的用户ID
   YOUR_SITE_URL = 'your_site_url'#可选
   YOUR_APP_NAME = 'your_app_name'#可选
   ```
   在根目录找到 `personalities.py` 文件，内容如下：
   ```python
   personalities = {
    "DefaultPersonality": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "prompt": "你是chatgpt。",
        "temperature": 0.6,
        "model": "openai/gpt-4o"
    },
   personalities = {
    "自定义人格的名字": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "prompt": "自定义人格提示词",
        "temperature": 1,
        "model": "openai/gpt-4o"
    },

   ```

4. **运行机器人**
   ```bash
   python bot.py
   ```

## 贡献

欢迎贡献！请随时提交拉取请求或打开问题，以讨论改进或错误。

## 许可证

此项目根据 MIT 许可证授权。

---

感谢您的使用！希望您享受增强的聊天体验。
