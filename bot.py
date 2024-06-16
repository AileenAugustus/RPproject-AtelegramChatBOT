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

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Store the current personality choice for each user
user_personalities = {}
# Store chat histories for each user
chat_histories = {}
# Store the last activity time for each user
last_activity = {}
# Store the timezone for each user
user_timezones = {}
# Store the scheduler task status for each user
scheduler_tasks = {}
# Store the important information for each user
user_memories = {}

# Get the latest personality choice
def get_latest_personality(chat_id):
    return user_personalities.get(chat_id, "DefaultPersonality")

# Handler function for the /start command
async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text(
        'Welcome to the chatbot!\n'
        'You can choose a personality using the following commands:\n'
        '/use DefaultPersonality - Switch to ChatGPT4o\n'
        '/use <personality name> - Switch to the specified personality\n'
        '/clear - Clear the current chat history\n'
        '/list - List your important information\n'
        '/list <number> <info> - Update your important information at the specified number\n'
        '/list del <number> - Delete your important information at the specified number\n'
        'Send a message to start chatting!\n'
        'You can also set your timezone, e.g., /time Asia/Shanghai'
    )
    last_activity[chat_id] = datetime.now()

    # Check if there's an existing scheduler task running, if so, cancel it
    if chat_id in scheduler_tasks:
        scheduler_tasks[chat_id].cancel()
        logger.info(f"Canceled existing greeting scheduler for chat_id: {chat_id}")

    # Start a new scheduler task
    logger.info(f"Starting new greeting scheduler for chat_id: {chat_id}")
    task = context.application.create_task(greeting_scheduler(chat_id, context))
    scheduler_tasks[chat_id] = task
    logger.info(f"greeting_scheduler task created for chat_id: {chat_id}")

# Handler function for the /use command
async def use_personality(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /use <personality name>')
        return

    personality_choice = args[0]
    if personality_choice in personalities:
        user_personalities[chat_id] = personality_choice
        await update.message.reply_text(f'Switched to {personality_choice} personality.')
        logger.info(f"User {chat_id} switched to personality {personality_choice}")
    else:
        await update.message.reply_text('Specified personality not found.')
        logger.warning(f"User {chat_id} tried to switch to unknown personality {personality_choice}")

# Handler function for the /time command
async def set_time(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /time <timezone name>')
        return

    timezone = args[0]
    try:
        # Attempt to set the timezone in the user_timezones dictionary
        pytz.timezone(timezone)
        user_timezones[chat_id] = timezone
        await update.message.reply_text(f'Timezone set to {timezone}')
        logger.info(f"User {chat_id} set timezone to {timezone}")
    except pytz.UnknownTimeZoneError:
        await update.message.reply_text('Invalid timezone name. Please use a valid timezone name, e.g., Asia/Shanghai')
        logger.warning(f"User {chat_id} tried to set unknown timezone {timezone}")

# Handler function for the /clear command
async def clear_history(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    chat_histories[chat_id] = []
    await update.message.reply_text('Cleared current chat history.')
    logger.info(f"Cleared chat history for chat_id: {chat_id}")

# Handler function for the /list command
async def list_memories(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) == 0:
        memories = user_memories.get(chat_id, [])
        if memories:
            response = "\n".join([f"{i+1}: {mem}" for i, mem in enumerate(memories)])
        else:
            response = "You have no stored memories."
        await update.message.reply_text(response)
    elif len(args) > 1 and args[0] != "del":
        index = int(args[0]) - 1
        info = " ".join(args[1:])
        if chat_id not in user_memories:
            user_memories[chat_id] = []
        if 0 <= index < 30:
            if index < len(user_memories[chat_id]):
                user_memories[chat_id][index] = info
            else:
                user_memories[chat_id].append(info)
            await update.message.reply_text(f"Memory updated at position {index + 1}.")
        else:
            await update.message.reply_text("Invalid position. Please choose a position between 1 and 30.")
    elif len(args) == 2 and args[0] == "del":
        index = int(args[1]) - 1
        if chat_id in user_memories and 0 <= index < len(user_memories[chat_id]):
            user_memories[chat_id].pop(index)
            await update.message.reply_text(f"Memory deleted at position {index + 1}.")
        else:
            await update.message.reply_text("Invalid position. Please choose a valid position to delete.")
    else:
        await update.message.reply_text("Usage: /list to view memories, /list <number> <info> to update memory, or /list del <number> to delete memory.")

# Function to handle messages
async def handle_message(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    message = update.message.text

    logger.info(f"Received message from {chat_id}: {message}")

    # Initialize chat history if not already present
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # Add new message to chat history
    chat_histories[chat_id].append(f"User: {message}")

    # Keep only the last 30 messages
    if len(chat_histories[chat_id]) > 30:
        chat_histories[chat_id].pop(0)

    # Update last activity time
    last_activity[chat_id] = datetime.now()

    # Get the current personality choice
    current_personality = get_latest_personality(chat_id)
    
    # Use default personality if the current one is undefined
    if current_personality not in personalities:
        current_personality = "DefaultPersonality"

    try:
        personality = personalities[current_personality]
    except KeyError:
        await update.message.reply_text(f"Cannot find personality: {current_personality}")
        logger.error(f"Personality {current_personality} not found for chat_id: {chat_id}")
        return

    # Send the personality prompt and recent chat history
    messages = [{"role": "system", "content": personality['prompt']}] + [{"role": "user", "content": msg} for msg in chat_histories[chat_id]]

    # Add user memories to the messages
    memories = user_memories.get(chat_id, [])
    for memory in memories:
        messages.append({"role": "user", "content": f"Remember: {memory}"})

    payload = {
        "model": personality['model'],
        "messages": messages,
        "temperature": personality['temperature']
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": YOUR_SITE_URL,  # Optional
        "X-Title": YOUR_APP_NAME  # Optional
    }

    logger.debug(f"Sending payload to API for chat_id {chat_id}: {json.dumps(payload, ensure_ascii=False)}")

    try:
        response = requests.post(personality['api_url'], headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Check if the HTTP request was successful
        logger.debug(f"API response for chat_id {chat_id}: {response.text}")

        response_json = response.json()
        reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        reply = f"HTTP error occurred: {http_err}"
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error occurred: {req_err}")
        reply = f"Request error occurred: {req_err}"
    except json.JSONDecodeError as json_err:
        logger.error(f"JSON decode error: {json_err}")
        reply = f"JSON decode error: {json_err}"
    except Exception as err:
        logger.error(f"An error occurred: {err}")
        reply = f"An error occurred: {err}"

    # Remove unnecessary prefixes (e.g., names)
    if "：" in reply:
        reply = reply.split("：", 1)[-1].strip()

    # Add the API response to the chat history
    chat_histories[chat_id].append(f"Bot: {reply}")

    logger.info(f"Replying to {chat_id}: {reply}")

    try:
        await update.message.reply_text(reply)
    except Exception as err:
        logger.error(f"Failed to send message: {err}")

async def greeting_scheduler(chat_id, context: CallbackContext):
    logger.info(f"greeting_scheduler started for chat_id: {chat_id}")
    while True:
        await asyncio.sleep(3600)  # Check for new messages every 60 seconds
        logger.info(f"Checking last activity for chat_id: {chat_id}")
        if chat_id in last_activity:
            delta = datetime.now() - last_activity[chat_id]
            logger.info(f"Time since last activity: {delta.total_seconds()} seconds")
            if delta.total_seconds() >= 3600:  # Last activity was over 1 minute ago
                logger.info(f"No activity detected for chat_id {chat_id} for 60 seconds.")
                wait_time = random.randint(3600, 14400)  # Wait randomly between 1 to 2 minutes
                logger.info(f"Waiting for {wait_time} seconds before sending greeting")
                await asyncio.sleep(wait_time)

                # Get the user's timezone
                timezone = user_timezones.get(chat_id, 'UTC')
                local_time = datetime.now(pytz.timezone(timezone)).strftime("%Y-%m-%d %H:%M:%S")
                greeting_message = f"It is now {local_time}, please generate and reply with a greeting or share your daily life. Please respond according to the given personality and character setting, following the examples below."

                # Generate the greeting
                examples = [
                    "0:00am-3:59am: 'Greet the user and ask if they are still awake.'",
                    "4:00am-5:59am: 'Please greet the user with Good morning and mention that you woke up early.'",
                    "6:00am-8:59am: 'Greet the user in the morning.'",
                    "9:00am-10:59am: 'Greet the user and ask what plans they have for today.'",
                    "11:00am-12:59pm: 'Ask the user if they would like to have lunch together.'",
                    "1:00pm-4:59pm: 'Talk about your work and express how much you miss the user.'",
                    "5:00pm-7:59pm: 'Ask the user if they would like to have dinner together.'",
                    "8:00pm-9:59pm: 'Describe your day or the beautiful evening scenery and ask about the user's day.'",
                    "10:00pm-11:59pm: 'Say goodnight to the user.'",
                    "Sharing daily life: 'Share your daily life or work.'"
                ]
                greeting_message += "\nFollow the style of the examples below for your reply, don't repeat the content of the examples, express it in your own way:\n" + "\n".join(examples)

                logger.info(f"Sending greeting message to chat_id {chat_id}: {greeting_message}")

                # Get the current personality choice
                current_personality = get_latest_personality(chat_id)
                if current_personality not in personalities:
                    current_personality = "DefaultPersonality"
                try:
                    personality = personalities[current_personality]
                except KeyError:
                    await context.bot.send_message(chat_id=chat_id, text=f"Cannot find personality: {current_personality}")
                    continue

                messages = [{"role": "system", "content": personality['prompt']}, {"role": "user", "content": greeting_message}]
                payload = {
                    "model": personality['model'],
                    "messages": messages,
                    "temperature": personality['temperature']
                }
                headers = {
                    "Authorization": f"Bearer {API_KEY}",
                    "HTTP-Referer": YOUR_SITE_URL,  # Optional
                    "X-Title": YOUR_APP_NAME  # Optional
                }

                logger.debug(f"Sending payload to API for chat_id {chat_id}: {json.dumps(payload, ensure_ascii=False)}")

                try:
                    response = requests.post(personality['api_url'], headers=headers, data=json.dumps(payload))
                    response.raise_for_status()
                    logger.debug(f"API response for chat_id {chat_id}: {response.text}")

                    response_json = response.json()
                    reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                    if "：" in reply:
                        reply = reply.split("：", 1)[-1].strip()
                    await context.bot.send_message(chat_id=chat_id, text=reply)

                    # Add the proactive greeting to the chat history
                    chat_histories[chat_id].append(f"Bot: {reply}")
                    last_activity[chat_id] = datetime.now()  # Update last activity time
                    logger.info(f"Greeting sent to chat_id {chat_id}: {reply}")
                except requests.exceptions.HTTPError as http_err:
                    logger.error(f"HTTP error occurred: {http_err}")
                except requests.exceptions.RequestException as req_err:
                    logger.error(f"Request error occurred: {req_err}")
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON decode error: {json_err}")
                except Exception as err:
                    logger.error(f"An error occurred: {err}")

# Main function
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Set commands
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("use", "Choose a personality"),
        BotCommand("clear", "Clear the current chat history"),
        BotCommand("time", "Set the timezone"),
        BotCommand("list", "Manage your important information")
    ]
    application.bot.set_my_commands(commands)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("use", use_personality))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(CommandHandler("time", set_time))
    application.add_handler(CommandHandler("list", list_memories))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
