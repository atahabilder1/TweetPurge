# TweetPurge

A Python CLI tool for bulk deleting tweets from a Twitter/X account using the Twitter API v2. Designed to help clean up an old timeline — whether for rebranding, privacy, or starting fresh.

## Why I Built This

I had 3,600+ old tweets on my account — random retweets, Facebook cross-posts, news shares from years ago — none of which reflected who I am today as a PhD student working in blockchain security and ML/LLMs. Manual deletion wasn't an option at that scale, and most third-party tools either cost money or felt sketchy with OAuth permissions. So I built my own.

## Features

- **Bulk deletion** of all tweets or a filtered subset from your account
- **Two data sources** for loading tweets:
  - **Twitter Data Archive** (recommended) — free, covers every tweet regardless of account age
  - **Twitter API v2 fetch** — limited to the ~3,200 most recent tweets, costs API credits
- **Resumable runs** — skips previously deleted tweets on re-run using a local deletion log, so you don't waste API credits retrying
- **Dry run mode** — preview what will be deleted before committing to anything
- **Smart rate limiting** — auto-pauses and resumes around Twitter's 50-request/15-min window
- **Early exit on billing errors** — stops immediately if your API credits or spend cap run out, instead of burning through the queue with failed requests
- **Deletion log** — every deleted tweet (text + metadata) is backed up to a local JSON file before removal
- **Flexible filters** — target tweets by date range (`--before`, `--after`) or content (`--contains`, `--exclude`)
- **Non-interactive mode** (`--yes`) — skip the confirmation prompt for unattended/scripted runs

## Tech Stack

- Python 3.12
- [Tweepy](https://www.tweepy.org/) — Twitter API v2 client
- [python-dotenv](https://github.com/theskumar/python-dotenv) — environment variable management
- Twitter API v2 with OAuth 1.0a User Context authentication

## Setup

```bash
git clone https://github.com/aniktahabilder/TweetPurge.git
cd TweetPurge

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Then fill in your Twitter API credentials (see below)
```

### Getting Twitter API Credentials

1. Go to [developer.x.com](https://developer.x.com) and sign up for a developer account
2. Create a new Project and App
3. Set app permissions to **Read and Write** (this is required for deleting tweets)
4. Under app type, select **Web App, Automated App or Bot**
5. Generate the following and paste them into your `.env` file:
   - **API Key** (Consumer Key)
   - **API Secret** (Consumer Secret)
   - **Access Token**
   - **Access Token Secret**
   - **Bearer Token** (optional, used for some read endpoints)

> **Important:** If you change your app permissions after generating tokens, you need to regenerate the Access Token and Access Token Secret for the new permissions to take effect.

## Usage

### Method 1: Using Your Twitter Data Archive (Recommended)

This is the most cost-effective approach — it avoids the expensive tweet-reading API calls entirely and covers your full tweet history.

1. Go to **X.com > Settings > Your Account > Download an archive of your data**
2. Wait for the archive to be ready (can take 24-48 hours)
3. Download and extract the `.zip` file
4. Find `tweets.js` inside the `data/` folder

```bash
# Preview what will be deleted (no actual deletions)
python delete_tweets.py --archive path/to/data/tweets.js --dry-run

# Delete all tweets from the archive
python delete_tweets.py --archive path/to/data/tweets.js

# Delete without confirmation prompt (for scripted/unattended runs)
python delete_tweets.py --archive path/to/data/tweets.js --yes
```

### Method 2: Using the API to Fetch Tweets

This fetches your recent tweets directly from the API. Limited to ~3,200 tweets and costs API credits for the read calls.

```bash
# Preview
python delete_tweets.py --dry-run

# Delete all fetched tweets
python delete_tweets.py
```

### Filtering

You can narrow down which tweets get deleted:

```bash
# Delete tweets posted before a specific date
python delete_tweets.py --archive data/tweets.js --before 2023-01-01

# Delete only tweets containing a keyword
python delete_tweets.py --archive data/tweets.js --contains "facebook.com"

# Combine filters: delete old tweets but keep ones mentioning something specific
python delete_tweets.py --archive data/tweets.js --before 2024-01-01 --exclude "research"

# Delete tweets posted after a date
python delete_tweets.py --archive data/tweets.js --after 2020-06-01
```

### Resuming After Interruption

The script logs every successful deletion to `deleted_tweets_log.json`. If you stop midway (rate limit, spend cap, Ctrl+C), just re-run the same command — it will automatically skip tweets that were already deleted and pick up where it left off.

## CLI Reference

| Flag | Description |
|------|-------------|
| `--archive PATH` | Path to `tweets.js` from your Twitter data archive |
| `--dry-run` | Preview deletions without actually deleting anything |
| `--yes` | Skip the confirmation prompt |
| `--before DATE` | Only delete tweets posted before this date (`YYYY-MM-DD`) |
| `--after DATE` | Only delete tweets posted after this date (`YYYY-MM-DD`) |
| `--contains TEXT` | Only delete tweets containing this text (case-insensitive) |
| `--exclude TEXT` | Skip tweets containing this text (case-insensitive) |

## API Cost Notes

The X/Twitter API uses a pay-per-use billing model. Here's a rough breakdown:

| Operation | Approximate Cost |
|-----------|-----------------|
| Reading tweets (API fetch) | ~$0.50 per 100 tweets |
| Deleting tweets | Significantly cheaper per request |
| Archive + delete only | Most cost-effective approach |

**Tip:** Set a spend cap in the developer portal under **Billing > Manage Spend Cap** to avoid unexpected charges. The script will detect when you've hit the cap and stop automatically instead of burning through failed requests.

## Project Structure

```
TweetPurge/
├── delete_tweets.py      # Main CLI tool
├── requirements.txt      # Python dependencies
├── .env.example          # Template for API credentials
├── .gitignore            # Keeps secrets and generated files out of version control
└── README.md
```

## Lessons Learned

- Twitter API v2 read endpoints are surprisingly expensive on pay-per-use (~$5 per 1,000 tweets fetched). Using the data archive as the source instead of API reads saves a lot.
- OAuth 1.0a Consumer Keys and Access Tokens are completely separate from OAuth 2.0 Client ID/Secret — mixing them up leads to confusing auth errors.
- Access Tokens must be regenerated after changing app permissions from Read-only to Read+Write. The old tokens won't carry the new permissions.
- Rate limit handling is non-negotiable — Twitter enforces a hard cap of 50 delete requests per 15-minute window.
- Resumability matters for long-running bulk operations. Logging deletions and skipping on re-run saved me from wasting credits on 3,600+ tweets.

## License

MIT

## Author

**Anik Tahabilder** — [@atahabilder1](https://x.com/atahabilder1)

PhD Student | Blockchain Security | ML & LLMs
