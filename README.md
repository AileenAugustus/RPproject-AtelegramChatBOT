# TelegramChatBOT
This repository contains a Telegram bot that interacts with users based on different personalities. Users can select different personalities for the bot, clear chat history, and the bot has a probability of sending automated messages if the user is inactive for a long time.
# Chatbot Telegram Bot

This repository contains a Telegram bot that interacts with users based on different personalities. Users can select different personalities for the bot, clear chat history, and the bot has a probability of sending automated messages if the user is inactive for a long time.

## Features

- Start the bot with a welcome message.
- Switch between different personalities using the `/use ` command.
- Clear the chat history with the `/clear ` command.
- The bot will automatically send messages if the user has been inactive for more than an hour.
- Stores user preferences and chat histories.

## Prerequisites

- Python 3.7+
- Telegram Bot Token (You can obtain this by creating a new bot through [BotFather](https://core.telegram.org/bots#botfather) on Telegram)
- API Key for the personality model service (OpenRouter API https://openrouter.ai/)

## Setup

1. **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/chatbot-telegram-bot.git
    cd chatbot-telegram-bot
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Configuration:**
    - Create a `config.py` file in the root directory with the following content:
    ```python
    API_KEY = 'your_api_key'
    TELEGRAM_BOT_TOKEN = 'your_telegram_bot_token'
    YOUR_SITE_URL = 'your_site_url'  # Optional
    YOUR_APP_NAME = 'your_app_name'  # Optional
    ```

    - Create a `personalities.py` file in the root directory with your defined personalities:
    ```python
    personalities = {
    "DefaultPersonality": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "prompt": "You are chatgpt",
        "temperature": 0.6,
        "model": "openai/gpt-4o"
    },
    "your friend": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "prompt": "insert your prompt here",
        "temperature": 1,
        "model": "openai/gpt-4o"
    },
    "more": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "prompt": "insert your prompt here",
        "temperature": 1,
        "model": "openai/gpt-4o"
    },
 
   }

    ```

## Running the Bot

To start the bot, simply run:

```bash
python bot.py
```

The bot will begin polling and you can interact with it through Telegram.

## Usage

### Commands

- **/start**: Start the bot and get a welcome message with instructions.
- **/use `<personality_name>`**: Switch the bot to use a specific personality.
    - Example: `/use DefaultPersonality`
- **/clear**: Clear the current chat history.

### Messaging

Send any text message to the bot to start a conversation. The bot will respond based on the currently selected personality and maintain a history of the conversation.

### Automated Messages

If the user has been inactive for more than an hour, the bot has a probability of sending automated messages. These messages are generated based on the selected personality and the time of day.

## Contributing

Feel free to fork the repository and submit pull requests. Contributions are welcome!

## Support

If you encounter any issues or have questions, please open an issue on GitHub.

## Acknowledgements

- Thanks to the [Python Telegram Bot](https://github.com/python-telegram-bot/python-telegram-bot) library for providing the Telegram bot API.
- Thanks to [OpenRouter](https://openrouter.ai/) for providing the API support.
- And other tools and libraries used.

---

Happy chatting!
