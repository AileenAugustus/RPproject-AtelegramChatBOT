import logging
import aiohttp
import json
import asyncio
import random
from datetime import datetime, timedelta
import pytz
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, JobQueue
from config import API_KEY, TELEGRAM_BOT_TOKEN, YOUR_SITE_URL, YOUR_APP_NAME, ALLOWED_USER_IDS
from personalities import personalities

# 启用日志记录
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 存储每个用户的当前人格选择
user_personalities = {}
# 存储每个用户的聊天历史
chat_histories = {}
# 存储每个用户的最后活动时间
last_activity = {}
# 存储每个用户的时区
user_timezones = {}
# 存储每个用户的记忆
user_memories = {}
# 存储每个用户的调度任务状态
scheduler_tasks = {}
# 存储每个用户的消息ID
message_ids = {}
# 存储每个用户的提醒
user_reminders = {}
# 存储每个用户的循环提醒
user_daily_reminders = {}


# 获取最新的人格选择
def get_latest_personality(chat_id):
    return user_personalities.get(chat_id, "DefaultPersonality")

# 装饰器函数来检查用户ID
def allowed_users_only(func):
    async def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if user_id in ALLOWED_USER_IDS:
            return await func(update, context)
        else:
            await update.message.reply_text("你没有权限使用此机器人。")
    return wrapper

# /start 命令的处理函数
@allowed_users_only
async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text(
        '欢迎使用聊天机器人！\n'
        '你可以使用以下命令选择人格：\n'
        '/use DefaultPersonality - 切换到 ChatGPT4o\n'
        '/use <personality name> - 切换到指定的人格\n'
        '/clear - 清除当前的聊天记录\n'
        '发送消息开始聊天吧！\n'
        '你也可以设置你的时区，例如 /time Asia/Shanghai\n'
        '使用/retry重新发送最后一条消息\n'
    )
    last_activity[chat_id] = datetime.now()

    # 检查是否有正在运行的调度任务，如果有则取消它
    if chat_id in scheduler_tasks:
        scheduler_tasks[chat_id].cancel()
        logger.info(f"取消了 chat_id: {chat_id} 的现有问候调度任务")

    # 启动一个新的调度任务
    logger.info(f"为 chat_id: {chat_id} 启动新的问候调度任务")
    task = context.application.create_task(greeting_scheduler(chat_id, context))
    scheduler_tasks[chat_id] = task
    logger.info(f"为 chat_id: {chat_id} 创建了 greeting_scheduler 任务")

# /use 命令的处理函数
@allowed_users_only
async def use_personality(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('用法: /use <personality name>')
        return

    personality_choice = args[0]
    if personality_choice in personalities:
        user_personalities[chat_id] = personality_choice
        await update.message.reply_text(f'切换到 {personality_choice} 人格。')
        logger.info(f"用户 {chat_id} 切换到人格 {personality_choice}")
    else:
        await update.message.reply_text('未找到指定的人格。')
        logger.warning(f"用户 {chat_id} 尝试切换到未知人格 {personality_choice}")

# /time 命令的处理函数
@allowed_users_only
async def set_time(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('用法: /time <timezone name>')
        return

    timezone = args[0]
    try:
        # 尝试在 user_timezones 字典中设置时区
        pytz.timezone(timezone)
        user_timezones[chat_id] = timezone
        await update.message.reply_text(f'时区设置为 {timezone}')
        logger.info(f"用户 {chat_id} 设置时区为 {timezone}")
    except pytz.UnknownTimeZoneError:
        await update.message.reply_text('无效的时区名称。请使用有效的时区名称，例如 Asia/Shanghai')
        logger.warning(f"用户 {chat_id} 尝试设置未知时区 {timezone}")

# /clear 命令的处理函数
@allowed_users_only
async def clear_history(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    chat_histories[chat_id] = []
    await update.message.reply_text('已清除当前的聊天记录。')
    logger.info(f"清除了 chat_id: {chat_id} 的聊天记录")

# /list 命令的处理函数
@allowed_users_only
async def list_memories(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args

    if not args:
        memories = user_memories.get(chat_id, [])
        if not memories:
            await update.message.reply_text('没有存储任何记忆。')
        else:
            memories_text = "\n".join([f"{i + 1}. {memory}" for i, memory in enumerate(memories)])
            await update.message.reply_text(f"记忆：\n{memories_text}")
    else:
        try:
            index = int(args[0]) - 1
            new_memory = " ".join(args[1:])
            if new_memory:
                if chat_id not in user_memories:
                    user_memories[chat_id] = []
                if 0 <= index < len(user_memories[chat_id]):
                    user_memories[chat_id][index] = new_memory
                elif index == len(user_memories[chat_id]):
                    user_memories[chat_id].append(new_memory)
                else:
                    await update.message.reply_text('无效的记忆索引。')
                    return
                await update.message.reply_text('记忆已更新。')
            else:
                if chat_id in user_memories and 0 <= index < len(user_memories[chat_id]):
                    del user_memories[chat_id][index]
                    await update.message.reply_text('记忆已删除。')
                else:
                    await update.message.reply_text('无效的记忆索引。')
        except (ValueError, IndexError):
            await update.message.reply_text('用法: /list <记忆索引> <新记忆文本>')

# /retry 命令的处理函数
@allowed_users_only
async def retry_last_response(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id

    try:
        # 确保聊天记录中至少有一个机器人响应
        if chat_id in chat_histories and len(chat_histories[chat_id]) > 1:
            # 查找最后一个机器人响应的索引
            last_bot_response_index = None
            for i in range(len(chat_histories[chat_id]) - 1, -1, -1):
                if chat_histories[chat_id][i].startswith("Bot:"):
                    last_bot_response_index = i
                    break

            if last_bot_response_index is not None:
                # 获取用户的原始消息
                last_user_message_index = last_bot_response_index - 1
                if last_user_message_index >= 0 and chat_histories[chat_id][last_user_message_index].startswith("User:"):
                    last_user_message = chat_histories[chat_id][last_user_message_index].split("User:", 1)[-1].strip()

                    # 从聊天记录中删除最后一个机器人响应
                    last_bot_response = chat_histories[chat_id].pop(last_bot_response_index)

                    logger.info(f"已从 chat_id {chat_id} 的聊天记录中删除最后一个机器人响应: {last_bot_response}")

                    # 删除Telegram中的最后一个机器人消息
                    if chat_id in message_ids and message_ids[chat_id]:
                        last_message_id = message_ids[chat_id].pop()
                        try:
                            await context.bot.delete_message(chat_id=chat_id, message_id=last_message_id)
                            logger.info(f"已删除 chat_id {chat_id} 的消息ID: {last_message_id}")
                        except Exception as delete_err:
                            logger.error(f"删除消息失败: {delete_err}")

                    # 检查记忆的相关性并重新请求API响应
                    await process_message(chat_id, last_user_message, update.message, context)

                else:
                    await context.bot.send_message(chat_id=chat_id, text="未找到对应的用户消息。")
            else:
                await context.bot.send_message(chat_id=chat_id, text="在聊天记录中未找到机器人响应以重试。")
        else:
            await context.bot.send_message(chat_id=chat_id, text="未找到聊天记录以重试。")

    except Exception as main_err:
        logger.error(f"处理消息时发生主要错误: {main_err}")
        await context.bot.send_message(chat_id=chat_id, text="处理消息时发生主要错误，请稍后重试。")

# /clock 命令的处理函数
@allowed_users_only
async def set_clock(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) < 2:
        await update.message.reply_text('用法: /clock <时间(HH:MM)> <事件>')
        return

    time_str = args[0]
    event = " ".join(args[1:])

    try:
        reminder_time = datetime.strptime(time_str, "%H:%M").time()
        if chat_id not in user_reminders:
            user_reminders[chat_id] = []
        user_reminders[chat_id].append((reminder_time, event))
        await update.message.reply_text(f'提醒已设置在 {time_str} 时提醒: {event}')
        logger.info(f"用户 {chat_id} 设置提醒在 {time_str} 时: {event}")
    except ValueError:
        await update.message.reply_text('无效的时间格式。请使用 HH:MM 格式。')
        logger.warning(f"用户 {chat_id} 尝试设置无效时间 {time_str}")

# /clocklist 命令的处理函数
@allowed_users_only
async def list_clocks(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    reminders = user_reminders.get(chat_id, [])
    if not reminders:
        await update.message.reply_text('没有设置任何提醒。')
    else:
        reminders_text = "\n".join([f"{i + 1}. {time.strftime('%H:%M')} - {event}" for i, (time, event) in enumerate(reminders)])
        await update.message.reply_text(f"提醒列表：\n{reminders_text}")

    daily_reminders = user_daily_reminders.get(chat_id, [])
    if daily_reminders:
        daily_reminders_text = "\n".join([f"{i + 1}. {time.strftime('%H:%M')} - {event}" for i, (time, event) in enumerate(daily_reminders)])
        await update.message.reply_text(f"每日提醒列表：\n{daily_reminders_text}")

# /clockeveryday 命令的处理函数
@allowed_users_only
async def set_daily_clock(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) < 2:
        await update.message.reply_text('用法: /clockeveryday <时间(HH:MM)> <事件>')
        return

    time_str = args[0]
    event = " ".join(args[1:])

    try:
        reminder_time = datetime.strptime(time_str, "%H:%M").time()
        if chat_id not in user_daily_reminders:
            user_daily_reminders[chat_id] = []
        user_daily_reminders[chat_id].append((reminder_time, event))
        await update.message.reply_text(f'每日提醒已设置在 {time_str} 时提醒: {event}')
        logger.info(f"用户 {chat_id} 设置每日提醒在 {time_str} 时: {event}")
    except ValueError:
        await update.message.reply_text('无效的时间格式。请使用 HH:MM 格式。')
        logger.warning(f"用户 {chat_id} 尝试设置无效时间 {time_str}")

# /clockclear 命令的处理函数
@allowed_users_only
async def clear_clock(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('用法: /clockclear <提醒索引>')
        return

    try:
        index = int(args[0]) - 1
        if chat_id in user_reminders and 0 <= index < len(user_reminders[chat_id]):
            del user_reminders[chat_id][index]
            await update.message.reply_text('提醒已删除。')
        else:
            await update.message.reply_text('无效的提醒索引或该索引对应的提醒不是一次性提醒。')
    except (ValueError, IndexError):
        await update.message.reply_text('无效的提醒索引。')

        
# /clockclearevery 命令的处理函数
@allowed_users_only
async def clear_daily_clock(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('用法: /clockclearevery <提醒索引>')
        return

    try:
        index = int(args[0]) - 1
        if chat_id in user_daily_reminders and 0 <= index < len(user_daily_reminders[chat_id]):
            del user_daily_reminders[chat_id][index]
            await update.message.reply_text('每日提醒已删除。')
        else:
            await update.message.reply_text('无效的提醒索引。')
    except (ValueError, IndexError):
        await update.message.reply_text('无效的提醒索引。')


# 消息处理函数
@allowed_users_only
async def handle_message(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    message = update.message.text

    logger.info(f"收到来自 {chat_id} 的消息: {message}")

    # 初始化聊天历史（如果尚未存在）
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # 将新消息添加到聊天历史
    chat_histories[chat_id].append(f"User: {message}")

    # 仅保留最近的30条消息
    if len(chat_histories[chat_id]) > 30:
        chat_histories[chat_id].pop(0)

    # 更新最后活动时间
    last_activity[chat_id] = datetime.now()

    # 取消当前的调度任务
    if chat_id in scheduler_tasks:
        scheduler_tasks[chat_id].cancel()
        logger.info(f"取消了 chat_id: {chat_id} 的现有问候调度任务")

    # 启动一个新的调度任务
    logger.info(f"为 chat_id: {chat_id} 启动新的问候调度任务")
    task = context.application.create_task(greeting_scheduler(chat_id, context))
    scheduler_tasks[chat_id] = task
    logger.info(f"为 chat_id: {chat_id} 创建了 greeting_scheduler 任务")

    await process_message(chat_id, message, update.message, context)

# 处理消息的函数，包括记忆检查
async def process_message(chat_id, message, telegram_message, context):
    # 获取当前的人格选择
    current_personality = get_latest_personality(chat_id)

    # 如果当前人格未定义，则使用默认人格
    if current_personality not in personalities:
        current_personality = "DefaultPersonality"

    try:
        personality = personalities[current_personality]
    except KeyError:
        await telegram_message.reply_text(f"找不到人格: {current_personality}")
        logger.error(f"找不到人格 {current_personality} 对于 chat_id: {chat_id}")
        return

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": YOUR_SITE_URL,  # 可选
        "X-Title": YOUR_APP_NAME  # 可选
    }

    # 准备记忆检查负载（如果有记忆）
    memories = user_memories.get(chat_id, [])
    if memories:
        memory_check_payload = {
            "model": personality['model'],
            "messages": [{"role": "user", "content": msg} for msg in chat_histories[chat_id]] + [{"role": "user", "content": f"记忆: {memory}"} for memory in memories] + [{"role": "user", "content": "请确定用户的消息与记忆之间的相关性。如果有相关性，请回复“1”，如果没有相关性，请回复“2”。"}],
            "temperature": personality['temperature']
        }

        logger.debug(f"为 chat_id {chat_id} 向API发送记忆检查负载: {json.dumps(memory_check_payload, ensure_ascii=False)}")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(personality['api_url'], headers=headers, json=memory_check_payload) as memory_check_response:
                    memory_check_response.raise_for_status()
                    memory_check_result = await memory_check_response.json()
                    logger.debug(f"chat_id {chat_id} 的记忆检查API响应: {memory_check_result}")

                    memory_check_result = memory_check_result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            except aiohttp.ClientResponseError as http_err:
                logger.error(f"HTTP 错误发生: {http_err}")
                memory_check_result = "2"
            except aiohttp.ClientError as req_err:
                logger.error(f"请求错误发生: {req_err}")
                memory_check_result = "2"
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON 解码错误: {json_err}")
                memory_check_result = "2"
            except Exception as err:
                logger.error(f"发生错误: {err}")
                memory_check_result = "2"

        # 如果记忆检查结果包含“1”，则在最终负载中包含记忆
        if "1" in memory_check_result:
            final_payload = {
                "model": personality['model'],
                "messages": [{"role": "system", "content": personality['prompt']}] + [{"role": "user", "content": msg} for msg in chat_histories[chat_id]] + [{"role": "user", "content": "每个记忆都是独立的，不要混淆它们。每次响应只使用一个相关的记忆。"}] + [{"role": "user", "content": f"记忆: {memory}"} for memory in memories],
                "temperature": personality['temperature']
            }
        else:
            final_payload = {
                "model": personality['model'],
                "messages": [{"role": "system", "content": personality['prompt']}] + [{"role": "user", "content": msg} for msg in chat_histories[chat_id]],
                "temperature": personality['temperature']
            }
    else:
        final_payload = {
            "model": personality['model'],
            "messages": [{"role": "system", "content": personality['prompt']}] + [{"role": "user", "content": msg} for msg in chat_histories[chat_id]],
            "temperature": personality['temperature']
        }

    logger.debug(f"为 chat_id {chat_id} 向API发送最终负载: {json.dumps(final_payload, ensure_ascii=False)}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(personality['api_url'], headers=headers, json=final_payload) as response:
                response.raise_for_status()  # 检查HTTP请求是否成功
                response_json = await response.json()
                logger.debug(f"chat_id {chat_id} 的API响应: {response_json}")

                reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        except aiohttp.ClientResponseError as http_err:
            logger.error(f"HTTP 错误发生: {http_err}")
            reply = f"HTTP 错误发生: {http_err}"
        except aiohttp.ClientError as req_err:
            logger.error(f"请求错误发生: {req_err}")
            reply = f"请求错误发生: {req_err}"
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON 解码错误: {json_err}")
            reply = f"JSON 解码错误: {json_err}"
        except Exception as err:
            logger.error(f"发生错误: {err}")
            reply = f"发生错误: {err}"

    # 移除不必要的前缀（例如，名字）
    if "：" in reply:
        reply = reply.split("：", 1)[-1].strip()

    # 将API响应添加到聊天历史
    chat_histories[chat_id].append(f"Bot: {reply}")

    logger.info(f"回复 {chat_id}: {reply}")

    try:
        sent_message = await telegram_message.reply_text(reply)
        # 记录消息ID
        if chat_id not in message_ids:
            message_ids[chat_id] = []
        message_ids[chat_id].append(sent_message.message_id)
    except Exception as err:
        logger.error(f"发送消息失败: {err}")


# 提醒调度程序
async def reminder_scheduler(context: CallbackContext):
    while True:
        await asyncio.sleep(60)  # 每60秒检查一次提醒
        now = datetime.now(pytz.utc)

        for chat_id, reminders in list(user_reminders.items()):
            timezone = user_timezones.get(chat_id, 'UTC')
            current_time = now.astimezone(pytz.timezone(timezone)).time()

            reminders_to_remove = []
            for reminder_time, reminder_text in reminders:
                if reminder_time <= current_time < (datetime.combine(datetime.today(), reminder_time) + timedelta(minutes=1)).time():
                    await send_reminder(chat_id, reminder_text, context)
                    reminders_to_remove.append((reminder_time, reminder_text))

            for reminder in reminders_to_remove:
                user_reminders[chat_id].remove(reminder)

        for chat_id, reminders in list(user_daily_reminders.items()):
            timezone = user_timezones.get(chat_id, 'UTC')
            current_time = now.astimezone(pytz.timezone(timezone)).time()

            for reminder_time, reminder_text in reminders:
                if reminder_time <= current_time < (datetime.combine(datetime.today(), reminder_time) + timedelta(minutes=1)).time():
                    await send_reminder(chat_id, reminder_text, context)

# 发送提醒的函数
async def send_reminder(chat_id, reminder_text, context: CallbackContext):
    logger.info(f"提醒时间到，向 chat_id {chat_id} 发送提醒内容: {reminder_text}")

    # 获取当前的人格选择
    current_personality = get_latest_personality(chat_id)
    if current_personality not in personalities:
        current_personality = "DefaultPersonality"
    try:
        personality = personalities[current_personality]
    except KeyError:
        await context.bot.send_message(chat_id=chat_id, text=f"找不到人格: {current_personality}")
        return

    # 将人格所有参数转换为字符串
    personality_details = "\n".join([f"{key}: {value}" for key, value in personality.items()])

    reminder_message = f"请提醒我应该做以下事情： {reminder_text} 遵守以下提示词：{personality['prompt']} 发送回复给我。"

    messages = [{"role": "system", "content": personality['prompt']}, {"role": "user", "content": reminder_message}]
    payload = {
        "model": personality['model'],
        "messages": messages,
        "temperature": personality['temperature']
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": YOUR_SITE_URL,  # 可选
        "X-Title": YOUR_APP_NAME  # 可选
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(personality['api_url'], headers=headers, json=payload) as response:
                response.raise_for_status()
                response_json = await response.json()
                reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                if "：" in reply:
                    reply = reply.split("：", 1)[-1].strip()
                sent_message = await context.bot.send_message(chat_id=chat_id, text=reply)
                # 将提醒内容和回复内容添加到聊天历史
                if chat_id not in chat_histories:
                    chat_histories[chat_id] = []
                chat_histories[chat_id].append(f"Reminder: {reminder_text}")
                chat_histories[chat_id].append(f"Bot: {reply}")

                # 记录消息ID
                if chat_id not in message_ids:
                    message_ids[chat_id] = []
                message_ids[chat_id].append(sent_message.message_id)

                last_activity[chat_id] = datetime.now()  # 更新最后活动时间
                logger.info(f"向 chat_id {chat_id} 发送了提醒: {reply}")
        except aiohttp.ClientResponseError as http_err:
            logger.error(f"HTTP 错误发生: {http_err}")
        except aiohttp.ClientError as req_err:
            logger.error(f"请求错误发生: {req_err}")
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON 解码错误: {json_err}")
        except Exception as err:
            logger.error(f"发生错误: {err}，消息内容: {reminder_text}，chat_id: {chat_id}")


# 问候调度程序
async def greeting_scheduler(chat_id, context: CallbackContext):
    logger.info(f"为 chat_id: {chat_id} 启动 greeting_scheduler")
    while True:
        await asyncio.sleep(600)  # 每3600秒检查一次新消息
        logger.info(f"检查 chat_id: {chat_id} 的最后活动时间")
        if chat_id in last_activity:
            delta = datetime.now() - last_activity[chat_id]
            logger.info(f"距离最后活动的时间: {delta.total_seconds()} 秒")
            if delta.total_seconds() >= 3600:  # 最后活动时间超过1小时
                logger.info(f"chat_id {chat_id} 在1小时内没有活动。")
                wait_time = random.randint(3600, 14400)  # 随机等待1到4小时
                logger.info(f"等待 {wait_time} 秒后发送问候")
                await asyncio.sleep(wait_time)

                # 获取用户的时区
                timezone = user_timezones.get(chat_id, 'UTC')
                local_time = datetime.now(pytz.timezone(timezone)).strftime("%Y-%m-%d %H:%M:%S")
                greeting_message = f"现在是 {local_time}，请生成并回复一个问候或分享你的日常生活。请根据给定的人格和角色设置回应，以下是一些示例。"

                # 生成问候
                examples = [
                    "0:00-3:59: '向用户问好，并询问他们是否还醒着。'",
                    "4:00-5:59: '请向用户说早上好，并提到你早起了。'",
                    "6:00-8:59: '在早上向用户问好。'",
                    "9:00-10:59: '向用户问好，并询问他们今天有什么计划。'",
                    "11:00-12:59: '询问用户是否已经吃过午饭。'",
                    "13:00-16:59: '谈谈你的工作，并表达你对用户的思念。'",
                    "17:00-19:59: '询问用户是否已经吃过晚饭。'",
                    "20:00-21:59: '描述你的一天或美丽的晚景，并询问用户的一天。'",
                    "22:00-23:59: '向用户说晚安。'",
                    "分享日常生活: '分享你的日常生活或工作。'"
                ]
                greeting_message += "\n按照示例的风格进行回复，不要重复示例的内容，用你自己的方式表达：\n" + "\n".join(examples)

                logger.info(f"向 chat_id {chat_id} 发送问候消息: {greeting_message}")

                # 获取当前的人格选择
                current_personality = get_latest_personality(chat_id)
                if current_personality not in personalities:
                    current_personality = "DefaultPersonality"
                try:
                    personality = personalities[current_personality]
                except KeyError:
                    await context.bot.send_message(chat_id=chat_id, text=f"找不到人格: {current_personality}")
                    continue

                messages = [{"role": "system", "content": personality['prompt']}, {"role": "user", "content": greeting_message}]
                payload = {
                    "model": personality['model'],
                    "messages": messages,
                    "temperature": personality['temperature']
                }
                headers = {
                    "Authorization": f"Bearer {API_KEY}",
                    "HTTP-Referer": YOUR_SITE_URL,  # 可选
                    "X-Title": YOUR_APP_NAME  # 可选
                }

                logger.debug(f"为 chat_id {chat_id} 向API发送负载: {json.dumps(payload, ensure_ascii=False)}")

                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(personality['api_url'], headers=headers, json=payload) as response:
                            response.raise_for_status()
                            response_json = await response.json()
                            logger.debug(f"chat_id {chat_id} 的API响应: {response_json}")

                            reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                            if "：" in reply:
                                reply = reply.split("：", 1)[-1].strip()
                            await context.bot.send_message(chat_id=chat_id, text=reply)

                            # 将主动问候添加到聊天历史
                            chat_histories[chat_id].append(f"Bot: {reply}")
                            last_activity[chat_id] = datetime.now()  # 更新最后活动时间
                            logger.info(f"向 chat_id {chat_id} 发送了问候: {reply}")
                    except aiohttp.ClientResponseError as http_err:
                        logger.error(f"HTTP 错误发生: {http_err}")
                    except aiohttp.ClientError as req_err:
                        logger.error(f"请求错误发生: {req_err}")
                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON 解码错误: {json_err}")
                    except Exception as err:
                        logger.error(f"发生错误: {err}")

# 主函数
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 设置命令
    commands = [
        BotCommand("start", "启动机器人"),
        BotCommand("use", "选择人格"),
        BotCommand("clear", "清除当前聊天记录"),
        BotCommand("time", "设置时区"),
        BotCommand("list", "列出和管理记忆"),
        BotCommand("retry", "重试最后一条消息"),
        BotCommand("clock", "设置提醒"),
        BotCommand("clocklist", "查看提醒列表"),
        BotCommand("clockeveryday", "设置每日提醒"),
        BotCommand("clockclear", "取消提醒"),
        BotCommand("clockclearevery", "取消每日提醒")
    ]
    application.bot.set_my_commands(commands)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("use", use_personality))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(CommandHandler("time", set_time))
    application.add_handler(CommandHandler("list", list_memories))
    application.add_handler(CommandHandler("retry", retry_last_response))
    application.add_handler(CommandHandler("clock", set_clock))
    application.add_handler(CommandHandler("clocklist", list_clocks))
    application.add_handler(CommandHandler("clockeveryday", set_daily_clock))
    application.add_handler(CommandHandler("clockclear", clear_clock))
    application.add_handler(CommandHandler("clockclearevery", clear_daily_clock))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 启动提醒调度任务
    job_queue = application.job_queue
    job_queue.run_repeating(reminder_scheduler, interval=60, first=10)

    application.run_polling()

if __name__ == '__main__':
    main()