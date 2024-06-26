# 扮演project
欢迎来到 扮演project 仓库！这个机器人允许用户与各种人格互动，设置时区，管理聊天记录等。它还具有问候调度功能，保持对话的活跃性。

## 功能

- **动态人格**：选择不同的人格以增强聊天体验。
- **记忆管理**：机器人可以记住之前的互动，并使用这些信息提供相关的回应。
- **时区设置**：设置您的时区以接收及时的问候和消息。
- **重试机制**：如果需要，可以重试最后的回应。
- **定时问候**：根据用户的活动和时区，机器人会定期发送问候消息。

## 命令

### 启动机器人
```
/start
```
启动机器人，并提供使用说明。

### 使用特定人格
```
/use <personality name>
```
切换到指定的人格，获得更有趣的对话体验。

### 清除聊天记录
```
/clear
```
清除当前的聊天记录。

### 设置时区
```
/time <timezone name>
```
设置您的时区（例如 `Asia/Shanghai`），以接收合适的问候消息。

### 列出和管理记忆
```
/list
```
列出所有存储的记忆。

```
/list <index> <new memory text>
```
通过索引更新或删除特定记忆。

### 重试最后的回应
```
/retry
```
重试最后的机器人回应，以防发生错误。

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
   YOUR_SITE_URL = 'your_site_url'#可选
   YOUR_APP_NAME = 'your_app_name'#可选
   ```
   在根目录找到 `personalities.py` 文件，内容如下：
   ```python
       # 在这里添加人格
   ```

4. **运行机器人**
   ```bash
   python bot.py
   ```

## 日志记录

启用日志记录以跟踪机器人的活动和错误。日志以不同级别（INFO、DEBUG、WARNING、ERROR）打印到控制台。

## 贡献

欢迎贡献！请随时提交拉取请求或打开问题，以讨论改进或错误。

## 许可证

此项目根据 MIT 许可证授权。

## 联系方式

如有任何问题或建议，请随时联系仓库所有者或打开问题。

---

感谢您的使用！希望您享受增强的聊天体验。
