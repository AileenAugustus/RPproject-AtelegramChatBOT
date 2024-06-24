# -*- coding: utf-8 -*-

import logging
import requests
import json
import asyncio
import random
from datetime import datetime
import pytz
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from config import API_KEY, TELEGRAM_BOT_TOKEN, YOUR_SITE_URL, YOUR_APP_NAME
from personalities import personalities

# 启用日志记录
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 存储每个用户当前的个性选择
user_personalities = {}
# 存储每个用户的聊天记录
chat_histories = {}
# 存储每个用户的最后活动时间
last_activity = {}
# 存储每个用户的时区
user_timezones = {}
# 存储每个用户的记忆
user_memories = {}
# 存储每个用户的调度任务状态
scheduler_tasks = {}

# 获取最新的个性选择
def get_latest_personality(chat_id):
    return user_personalities.get(chat_id, "DefaultPersonality")

# /start 命令的处理函数
async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text(
        '欢迎使用聊天机器人！\n'
        '你可以使用以下命令选择一个个性：\n'
        '/use DefaultPersonality - 切换到 ChatGPT4o\n'
        '/use <个性名称> - 切换到指定个性\n'
        '/clear - 清除当前聊天记录\n'
        '/retry - 重新获取回复\n'
        '/list - 记忆列表\n'
        '发送消息开始聊天吧！\n'
        '你还可以设置你的时区，例如：/time Asia/Shanghai'
    )
    last_activity[chat_id] = datetime.now()

    # 如果有正在运行的调度任务，取消它
    if chat_id in scheduler_tasks:
        scheduler_tasks[chat_id].cancel()
        logger.info(f"取消现有的问候调度任务，chat_id: {chat_id}")

    # 启动一个新的调度任务
    logger.info(f"启动新的问候调度任务，chat_id: {chat_id}")
    task = context.application.create_task(greeting_scheduler(chat_id, context))
    scheduler_tasks[chat_id] = task
    logger.info(f"问候调度任务已为 chat_id {chat_id} 创建")

# /use 命令的处理函数
async def use_personality(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('用法: /use <个性名称>')
        return

    personality_choice = args[0]
    if personality_choice in personalities:
        user_personalities[chat_id] = personality_choice
        await update.message.reply_text(f'切换到 {personality_choice} 个性。')
        logger.info(f"用户 {chat_id} 切换到个性 {personality_choice}")
    else:
        await update.message.reply_text('指定的个性未找到。')
        logger.warning(f"用户 {chat_id} 尝试切换到未知个性 {personality_choice}")

# /time 命令的处理函数
async def set_time(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('用法: /time <时区名称>')
        return

    timezone = args[0]
    try:
        # 尝试在 user_timezones 字典中设置时区
        pytz.timezone(timezone)
        user_timezones[chat_id] = timezone
        await update.message.reply_text(f'时区设置为 {timezone}')
        logger.info(f"用户 {chat_id} 设置时区为 {timezone}")
    except pytz.UnknownTimeZoneError:
        await update.message.reply_text('无效的时区名称。请使用有效的时区名称，例如：Asia/Shanghai')
        logger.warning(f"用户 {chat_id} 尝试设置未知时区 {timezone}")

# /clear 命令的处理函数
async def clear_history(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    chat_histories[chat_id] = []
    await update.message.reply_text('已清除当前聊天记录。')
    logger.info(f"已清除 chat_id 为 {chat_id} 的聊天记录")

# /list 命令的处理函数
async def list_memories(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args

    if not args:
        memories = user_memories.get(chat_id, [])
        if not memories:
            await update.message.reply_text('没有存储的记忆。')
        else:
            memories_text = "\n".join([f"{i + 1}. {memory}" for i, memory in enumerate(memories)])
            await update.message.reply_text(f"记忆:\n{memories_text}")
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

# 存储每个用户的消息ID
message_ids = {}

# 处理消息的函数
async def handle_message(update: Update, context: CallbackContext, reprocessing=False) -> str:
    chat_id = update.message.chat_id
    if reprocessing:
        message = update.message.reply_to_message.text
    else:
        message = update.message.text

    logger.info(f"收到来自 {chat_id} 的消息: {message}")

    # 如果聊天记录尚不存在，则初始化
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # 添加新消息到聊天记录
    if not reprocessing:
        chat_histories[chat_id].append(f"User: {message}")

    # 仅保留最近的30条消息
    if len(chat_histories[chat_id]) > 30:
        chat_histories[chat_id].pop(0)

    # 更新最后活动时间
    last_activity[chat_id] = datetime.now()

    # 获取当前的个性选择
    current_personality = get_latest_personality(chat_id)
    
    # 如果当前个性未定义，则使用默认个性
    if current_personality not in personalities:
        current_personality = "DefaultPersonality"

    try:
        personality = personalities[current_personality]
    except KeyError:
        await update.message.reply_text(f"找不到个性: {current_personality}")
        logger.error(f"个性 {current_personality} 未找到，chat_id: {chat_id}")
        return

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": YOUR_SITE_URL,  # 可选
        "X-Title": YOUR_APP_NAME  # 可选
    }

    final_payload = {
        "model": personality['model'],
        "messages": [{"role": "system", "content": personality['prompt']}] + [{"role": "user", "content": msg} for msg in chat_histories[chat_id]],
        "temperature": personality['temperature']
    }

    logger.debug(f"发送最终负载到API，chat_id {chat_id}: {json.dumps(final_payload, ensure_ascii=False)}")

    try:
        response = requests.post(personality['api_url'], headers=headers, data=json.dumps(final_payload))
        response.raise_for_status()  # 检查HTTP请求是否成功
        logger.debug(f"API响应，chat_id {chat_id}: {response.text}")

        response_json = response.json()
        reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"发生HTTP错误: {http_err}")
        reply = f"HTTP错误发生: {http_err}"
    except requests.exceptions.RequestException as req_err:
        logger.error(f"请求错误发生: {req_err}")
        reply = f"请求错误发生: {req_err}"
    except json.JSONDecodeError as json_err:
        logger.error(f"JSON解码错误: {json_err}")
        reply = f"JSON解码错误: {json_err}"
    except Exception as err:
        logger.error(f"发生错误: {err}")
        reply = f"发生错误: {err}"

    # 删除不必要的前缀（例如，名字）
    if "：" in reply:
        reply = reply.split("：", 1)[-1].strip()

    logger.debug(f"原始回复: {reply}")
    if "：" in reply:
        split_result = reply.split("：", 1)
        logger.debug(f"分割结果: {split_result}")
        if len(split_result) > 1:
            reply = split_result[-1].strip()
            logger.debug(f"处理后的回复: {reply}")
        else:
            logger.debug("未找到分割点")
    else:
        logger.debug("回复中未找到 '：'")

    if not reprocessing:
        # 添加API响应到聊天记录
        chat_histories[chat_id].append(f"Bot: {reply}")

    logger.info(f"回复给 {chat_id}: {reply}")

    try:
        sent_message = await update.message.reply_text(reply)
        # 记录机器人的消息ID
        if chat_id not in message_ids:
            message_ids[chat_id] = []
        message_ids[chat_id].append(sent_message.message_id)
    except Exception as err:
        logger.error(f"发送消息失败: {err}")

    return reply


    # 删除不必要的前缀（例如，名字）
    if "：" in reply:
        reply = reply.split("：", 1)[-1].strip()

    logger.debug(f"原始回复: {reply}")
    if "：" in reply:
        split_result = reply.split("：", 1)
        logger.debug(f"分割结果: {split_result}")
        if len(split_result) > 1:
            reply = split_result[-1].strip()
            logger.debug(f"处理后的回复: {reply}")
        else:
            logger.debug("未找到分割点")
    else:
        logger.debug("回复中未找到 '：'")

    if not reprocessing:
        # 添加API响应到聊天记录
        chat_histories[chat_id].append(f"Bot: {reply}")

    logger.info(f"回复给 {chat_id}: {reply}")

    try:
        await update.message.reply_text(reply)
    except Exception as err:
        logger.error(f"发送消息失败: {err}")

    return reply

# /retry 命令的处理函数
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

                    # 使用更新后的聊天记录重新请求API响应
                    try:
                        # 获取当前的个性选择
                        current_personality = get_latest_personality(chat_id)
                        if current_personality not in personalities:
                            current_personality = "DefaultPersonality"

                        personality = personalities[current_personality]

                        messages = [
                            {"role": "system", "content": personality['prompt']},
                            {"role": "user", "content": last_user_message}
                        ]
                        payload = {
                            "model": personality['model'],
                            "messages": messages,
                            "temperature": personality['temperature']
                        }
                        headers = {
                            "Authorization": f"Bearer {API_KEY}",
                            "HTTP-Referer": YOUR_SITE_URL,  # 可选，根据需要添加
                            "X-Title": YOUR_APP_NAME  # 可选，根据需要添加
                        }

                        logger.debug(f"发送负载到API，chat_id {chat_id}: {json.dumps(payload, ensure_ascii=False)}")

                        response = requests.post(personality['api_url'], headers=headers, data=json.dumps(payload))
                        response.raise_for_status()
                        logger.debug(f"API响应，chat_id {chat_id}: {response.text}")

                        response_json = response.json()
                        reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                        if "：" in reply:
                            reply = reply.split("：", 1)[-1].strip()

                        # 将新的 API 回复添加到聊天记录
                        chat_histories[chat_id].append(f"Bot: {reply}")

                        # 发送新的 API 回复到 Telegram
                        sent_message = await context.bot.send_message(chat_id=chat_id, text=reply)
                        # 记录新的消息ID
                        message_ids[chat_id].append(sent_message.message_id)

                    except requests.exceptions.HTTPError as http_err:
                        logger.error(f"发生HTTP错误: {http_err}")
                        await context.bot.send_message(chat_id=chat_id, text=f"HTTP错误发生: {http_err}")

                    except requests.exceptions.RequestException as req_err:
                        logger.error(f"请求错误发生: {req_err}")
                        await context.bot.send_message(chat_id=chat_id, text=f"请求错误发生: {req_err}")

                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON解码错误: {json_err}")
                        await context.bot.send_message(chat_id=chat_id, text=f"JSON解码错误: {json_err}")

                    except Exception as err:
                        logger.error(f"发生错误: {err}")
                        await context.bot.send_message(chat_id=chat_id, text=f"发生错误: {err}")
                else:
                    await context.bot.send_message(chat_id=chat_id, text="未找到对应的用户消息。")
            else:
                await context.bot.send_message(chat_id=chat_id, text="在聊天记录中未找到机器人响应以重试。")
        else:
            await context.bot.send_message(chat_id=chat_id, text="未找到聊天记录以重试。")

    except Exception as main_err:
        logger.error(f"处理消息时发生主要错误: {main_err}")
        await context.bot.send_message(chat_id=chat_id, text="处理消息时发生主要错误，请稍后重试。")


# 问候调度任务函数
async def greeting_scheduler(chat_id, context: CallbackContext):
    logger.info(f"问候调度任务已启动，chat_id: {chat_id}")
    while True:
        await asyncio.sleep(1800)  # 每1800秒检查一次新消息
        logger.info(f"检查 chat_id {chat_id} 的最后活动时间")
        if chat_id in last_activity:
            delta = datetime.now() - last_activity[chat_id]
            logger.info(f"自上次活动以来的时间: {delta.total_seconds()} 秒")
            if delta.total_seconds() >= 3600:  # 最后一次活动超过3600秒
                logger.info(f"检测到 chat_id {chat_id} 在60秒内无活动。")
                wait_time = random.randint(3600, 14400)  # 随机等待2到4小时
                logger.info(f"等待 {wait_time} 秒后发送问候")

                await asyncio.sleep(wait_time)

                # 获取用户的时区
                timezone = user_timezones.get(chat_id, 'UTC')
                local_time = datetime.now(pytz.timezone(timezone)).strftime("%Y-%m-%d %H:%M:%S")
                greeting_message = f"现在是 {local_time}，请生成并回复一个问候并分享你的日常生活。请根据给定的个性和角色设置进行回应，遵循以下示例风格。"

                # 生成问候语
                examples = [
                    "0:00-3:59: '向用户问好并询问他们是否已经入睡。'",
                    "4:00-5:59: '请向用户道早安，提到你早起，并询问他们是否还在睡觉。'",
                    "6:00-8:59: '在早上向用户问好。'",
                    "9:00-10:59: '询问用户今天有什么计划。'",
                    "11:00-12:59: '询问用户是否愿意和你共进午餐。'",
                    "13:00-16:59: '谈论你的日常生活并表达对用户的想念。'",
                    "17:00-19:59: '询问用户是否愿意和你共进晚餐。'",
                    "20:00-21:59: '描述你的一天或美丽的夜晚景色。'",
                    "22:00-23:59: '向用户道晚安。'",
                    "分享日常生活: '分享你的日常生活或工作。'"
                ]
                greeting_message += "\n请遵循以下示例的风格进行回复，不要重复示例内容，用你自己的方式表达:\n" + "\n".join(examples)

                logger.info(f"发送问候消息给 chat_id {chat_id}: {greeting_message}")

                # 获取当前的个性选择
                current_personality = get_latest_personality(chat_id)
                if current_personality not in personalities:
                    current_personality = "DefaultPersonality"
                try:
                    personality = personalities[current_personality]
                except KeyError:
                    await context.bot.send_message(chat_id=chat_id, text=f"找不到个性: {current_personality}")
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

                logger.debug(f"发送负载到API，chat_id {chat_id}: {json.dumps(payload, ensure_ascii=False)}")

                try:
                    response = requests.post(personality['api_url'], headers=headers, data=json.dumps(payload))
                    response.raise_for_status()
                    logger.debug(f"API响应，chat_id {chat_id}: {response.text}")

                    response_json = response.json()
                    reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                    if "：" in reply:
                        reply = reply.split("：", 1)[-1].strip()
                    await context.bot.send_message(chat_id=chat_id, text=reply)

                    # 将主动问候添加到聊天记录
                    chat_histories[chat_id].append(f"Bot: {reply}")
                    last_activity[chat_id] = datetime.now()  # 更新最后活动时间
                    logger.info(f"问候已发送给 chat_id {chat_id}: {reply}")
                except requests.exceptions.HTTPError as http_err:
                    logger.error(f"发生HTTP错误: {http_err}")
                except requests.exceptions.RequestException as req_err:
                    logger.error(f"请求错误发生: {req_err}")
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON解码错误: {json_err}")
                except Exception as err:
                    logger.error(f"发生错误: {err}")

# 主函数
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 设置命令
    commands = [
        BotCommand("start", "启动机器人"),
        BotCommand("use", "选择一个个性"),
        BotCommand("clear", "清除当前聊天记录"),
        BotCommand("time", "设置时区"),
        BotCommand("list", "列出和管理记忆"),
        BotCommand("retry", "重试最后一个机器人响应")
    ]
    application.bot.set_my_commands(commands)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("use", use_personality))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(CommandHandler("time", set_time))
    application.add_handler(CommandHandler("list", list_memories))
    application.add_handler(CommandHandler("retry", retry_last_response))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
