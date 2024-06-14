# -*- coding: utf-8 -*-

import logging
import requests
import json
import asyncio
import random
from datetime import datetime
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from config import API_KEY, TELEGRAM_BOT_TOKEN, YOUR_SITE_URL, YOUR_APP_NAME
from personalities import personalities

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Store the current personality chosen by each user
user_personalities = {}
# Store the chat history of each user
chat_histories = {}
# Store the last activity time of each user
last_activity = {}
# Store the status of scheduling tasks for each user
scheduler_tasks = {}

# Get the latest personality choice
def get_latest_personality(chat_id):
    return user_personalities.get(chat_id, "DefaultPersonality")

# Handler function for the /start command
async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text(
        'Welcome to the chatbot!\n'
        'You can choose a personality with the following commands:\n'
        '/use DefaultPersonality - Switch to ChatGPT4o\n'
        '/use <Personality Name> - Switch to the specified personality\n'
        '/clear - Clear the current chat history\n'
        'Send a message to start chatting!'
    )
    last_activity[chat_id] = datetime.now()

    # Check if a scheduling task is already running, if so, cancel it
    if chat_id in scheduler_tasks:
        scheduler_tasks[chat_id].cancel()
        logger.info(f"Canceled existing greeting scheduler for chat_id: {chat_id}")

    # Start a new scheduling task
    logger.info(f"Starting new greeting scheduler for chat_id: {chat_id}")
    task = context.application.create_task(greeting_scheduler(chat_id, context))
    scheduler_tasks[chat_id] = task
    logger.info(f"greeting_scheduler task created for chat_id: {chat_id}")

# Handler function for the /use command
async def use_personality(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /use <Personality Name>')
        return

    personality_choice = args[0]
    if personality_choice in personalities:
        user_personalities[chat_id] = personality_choice
        await update.message.reply_text(f'Switched to {personality_choice} personality.')
        logger.info(f"User {chat_id} switched to personality {personality_choice}")
    else:
        await update.message.reply_text('Specified personality not found.')
        logger.warning(f"User {chat_id} tried to switch to unknown personality {personality_choice}")

# Handler function for the /clear command
async def clear_history(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    chat_histories[chat_id] = []
    await update.message.reply_text('Cleared the current chat history.')
    logger.info(f"Cleared chat history for chat_id: {chat_id}")

# Function to handle messages
async def handle_message(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    message = update.message.text

    logger.info(f"Received message from {chat_id}: {message}")

    # Initialize records in the chat history dictionary
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # Add the new message to the chat history
    chat_histories[chat_id].append(f"User: {message}")

    # Keep the last 30 records
    if len(chat_histories[chat_id]) > 30:
        chat_histories[chat_id].pop(0)

    # Update the last activity time
    last_activity[chat_id] = datetime.now()

    # Get the current personality choice
    current_personality = get_latest_personality(chat_id)
    
    # If the current personality is not defined, use the default personality
    if current_personality not in personalities:
        current_personality = "DefaultPersonality"

    try:
        personality = personalities[current_personality]
    except KeyError:
        await update.message.reply_text(f"Personality not found: {current_personality}")
        logger.error(f"Personality {current_personality} not found for chat_id: {chat_id}")
        return

    # Send the personality prompt and the recent chat history
    messages = [{"role": "system", "content": personality['prompt']}] + [{"role": "user", "content": msg} for msg in chat_histories[chat_id]]

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
    if ":" in reply:
        reply = reply.split(":", 1)[-1].strip()

    # Add the API reply to the chat history
    chat_histories[chat_id].append(f"Bot: {reply}")

    logger.info(f"Replying to {chat_id}: {reply}")

    try:
        await update.message.reply_text(reply)
    except Exception as err:
        logger.error(f"Failed to send message: {err}")

async def greeting_scheduler(chat_id, context: CallbackContext):
    logger.info(f"greeting_scheduler started for chat_id: {chat_id}")  # Added logging
    while True:
        await asyncio.sleep(3600)  # Interval for checking new messages
        logger.info(f"Checking last activity for chat_id: {chat_id}")
        if chat_id in last_activity:
            delta = datetime.now() - last_activity[chat_id]
            logger.info(f"Time since last activity: {delta.total_seconds()} seconds")
            if delta.total_seconds() >= 3600:  # Last activity time exceeds threshold
                logger.info(f"No activity detected for chat_id {chat_id} for 60 seconds.")
                wait_time = random.randint(3600, 14400)  # Random wait time
                logger.info(f"Waiting for {wait_time} seconds before sending greeting")
                await asyncio.sleep(wait_time)
                local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                greeting_message = f"It is now {local_time}, please generate and reply with a greeting or share your daily routine."

                # Generate greeting examples
                examples = [
                    "For lunchtime, you can send like this: 'Hey friend, are you there? I would like to invite you to lunch.'",
                    "In the morning, you can send send like this: 'Good morning! Hope you have a great day!'",
                    "After 10 PM, you can send send like this: 'Good night, friend, have a good dream!'",
                    "After 0 AM, you can send send like this: 'Are you still awake? Friend?'",
                    "To share your daily routine, you can send send like this: 'Guess what I found today?'"
                ]
                greeting_message += "\nRespond with a message in the style of the following examples:\n" + "\n".join(examples)

                logger.info(f"Sending greeting message to chat_id {chat_id}: {greeting_message}")

                # Get the current personality choice
                current_personality = get_latest_personality(chat_id)
                if current_personality not in personalities:
                    current_personality = "DefaultPersonality"
                try:
                    personality = personalities[current_personality]
                except KeyError:
                    await context.bot.send_message(chat_id=chat_id, text=f"Personality not found: {current_personality}")
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
                    if ":" in reply:
                        reply = reply.split(":", 1)[-1].strip()
                    await context.bot.send_message(chat_id=chat_id, text=reply)

                    # Add the proactive greeting to the chat history
                    chat_histories[chat_id].append(f"Bot: {reply}")
                    last_activity[chat_id] = datetime.now()  # Update the last activity time
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
        BotCommand("clear", "Clear the current chat history")
    ]
    application.bot.set_my_commands(commands)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("use", use_personality))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
