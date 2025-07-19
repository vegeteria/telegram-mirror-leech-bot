# Mirror Leech Telegram Bot

This is a Telegram bot that can mirror files from various sources to Google Drive and other cloud storage services. It can also leech files from the internet and upload them to Telegram.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

* Python 3.8 or higher
* A Telegram account
* A Google account

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your_username/mirror-leech-telegram-bot.git
   ```
2. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Install system dependencies:**
   ```bash
   sudo apt-get install -y aria2
   ```
4. **Set up your environment variables:**
   Create a `.env` file in the root directory of the project and add the following variables:
   ```
   API_ID=your_api_id
   API_HASH=your_api_hash
   BOT_TOKEN=your_bot_token
   OWNER_ID=your_owner_id
   ```
   You can get your `API_ID` and `API_HASH` from [my.telegram.org](https.my.telegram.org). You can get your `BOT_TOKEN` from [BotFather](https://t.me/botfather). Your `OWNER_ID` is your Telegram user ID.

5. **Generate a Jarvis_Session.session file:**
   Run the `bot.py` file once to generate a `Jarvis_Session.session` file.
   ```bash
   python3 bot.py
   ```
   You will be prompted to enter your phone number, and then a code that you will receive on Telegram.

### Usage

To start the bot, run the following command:
```bash
python3 bot.py
```

## Commands

Here is a list of the available commands:

| Command | Description |
| --- | --- |
| `/mirror` | Mirror a file to Google Drive. |
| `/leech` | Leech a file from the internet and upload it to Telegram. |
| `/ytdlp` | Download a video from YouTube and other sites. |
| `/status` | Show the status of all downloads. |
| `/cancel` | Cancel a download. |
| `/list` | List all files in a Google Drive folder. |
| `/search` | Search for a file in Google Drive. |
| `/help` | Show this help message. |

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
