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
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Store the current personality selection for each user
user_personalities = {}
# Store the chat history for each user
chat_histories = {}
# Store the last activity time for each user
last_activity = {}

# Get the latest personality selection
def get_latest_personality(chat_id):
    return user_personalities.get(chat_id, "DefaultPersonality")

# Handler for the /start command
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        'Welcome to the chatbot!\n'
        'You can choose a personality using the following commands:\n'
        '/use DefaultPersonality - Switch to ChatGPT4o\n'
        '/use <personality_name> - Switch to the specified personality\n'
        '/clear - Clear the current chat history\n'
        'Send a message to start chatting!'
    )
    chat_id = update.message.chat_id
    last_activity[chat_id] = datetime.now()
    context.application.create_task(greeting_scheduler(chat_id, context))

# Handler for the /use command
async def use_personality(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text('Usage: /use <personality_name>')
        return

    personality_choice = args[0]
    if personality_choice in personalities:
        user_personalities[chat_id] = personality_choice
        await update.message.reply_text(f'Switched to {personality_choice} personality.')
    else:
        await update.message.reply_text('Specified personality not found.')

# Handler for the /clear command
async def clear_history(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    chat_histories[chat_id] = []
    await update.message.reply_text('Cleared current chat history.')

# Function to handle messages
async def handle_message(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    message = update.message.text

    # Initialize records in the chat history dictionary
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # Add the new message to the chat history
    chat_histories[chat_id].append(f"User: {message}")

    # Keep only the last 30 records
    if len(chat_histories[chat_id]) > 30:
        chat_histories[chat_id].pop(0)

    # Update the last activity time
    last_activity[chat_id] = datetime.now()

    # Get the current personality selection
    current_personality = get_latest_personality(chat_id)
    
    # Use the default personality if the current one is not defined
    if current_personality not in personalities:
        current_personality = "DefaultPersonality"

    try:
        personality = personalities[current_personality]
    except KeyError:
        await update.message.reply_text(f"Cannot find personality: {current_personality}")
        return

    # Send the personality prompt and recent chat history
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

    try:
        response = requests.post(personality['api_url'], headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Check if the HTTP request was successful
        logging.info(response.text)  # Print the response content for debugging

        response_json = response.json()
        reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        reply = f"HTTP error occurred: {http_err}"
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Request error occurred: {req_err}")
        reply = f"Request error occurred: {req_err}"
    except json.JSONDecodeError as json_err:
        logging.error(f"JSON decode error: {json_err}")
        reply = f"JSON decode error: {json_err}"
    except Exception as err:
        logging.error(f"An error occurred: {err}")
        reply = f"An error occurred: {err}"

    # Remove unnecessary prefixes (e.g., names)
    if "：" in reply:
        reply = reply.split("：", 1)[-1].strip()

    # Add the API's reply to the chat history
    chat_histories[chat_id].append(f"Bot: {reply}")

    try:
        await update.message.reply_text(reply)
    except Exception as err:
        logging.error(f"Failed to send message: {err}")

async def greeting_scheduler(chat_id, context: CallbackContext):
    while True:
        await asyncio.sleep(3600)  # Check for new messages every 1 hour
        if chat_id in last_activity:
            delta = datetime.now() - last_activity[chat_id]
            if delta.total_seconds() >= 3600:  # Last activity was over 1 hour ago
                wait_time = random.randint(2, 7) * 3600  # Random wait time between 2 to 7 hours
                await asyncio.sleep(wait_time)
                local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                greeting_message = f"Now it is {local_time}, please generate and reply with a greeting or share your daily life."

                # Example greetings
                examples = [
                    "For lunchtime, you can send like this: 'Friend, are you there? I want to invite you for lunch.'",
                    "For the morning, you can send like this: 'Good morning! Hope you have a great day!'",
                    "After 10 PM, you can send like this: 'Good night, friend, sweet dreams!'",
                    "To share daily life, you can send like this: 'Friend, guess what I found?'"
                ]
                greeting_message += "\nReply in the style of the following examples:\n" + "\n".join(examples)

                # Get the current personality selection
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

                try:
                    response = requests.post(personality['api_url'], headers=headers, data=json.dumps(payload))
                    response.raise_for_status()
                    response_json = response.json()
                    reply = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                    if "：" in reply:
                        reply = reply.split("：", 1)[-1].strip()
                    await context.bot.send_message(chat_id=chat_id, text=reply)

                    # Add the proactive greeting reply to the chat history
                    chat_histories[chat_id].append(f"Bot: {reply}")
                except requests.exceptions.HTTPError as http_err:
                    logging.error(f"HTTP error occurred: {http_err}")
                except requests.exceptions.RequestException as req_err:
                    logging.error(f"Request error occurred: {req_err}")
                except json.JSONDecodeError as json_err:
                    logging.error(f"JSON decode error: {json_err}")
                except Exception as err:
                    logging.error(f"An error occurred: {err}")

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
