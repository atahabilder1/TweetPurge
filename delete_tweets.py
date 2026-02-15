#!/usr/bin/env python3
"""
Tweet Deletion Tool
Delete all tweets (or filtered tweets) from your Twitter/X account.

Usage:
    # Dry run first (see what would be deleted, no actual deletion)
    python delete_tweets.py --dry-run

    # Delete all tweets fetched via API (limited to ~3200 most recent)
    python delete_tweets.py

    # Delete using Twitter data archive (gets ALL tweets)
    python delete_tweets.py --archive path/to/tweets.js

    # Delete tweets older than a specific date
    python delete_tweets.py --before 2023-01-01

    # Delete tweets containing specific keywords
    python delete_tweets.py --contains "facebook.com"
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import tweepy
from dotenv import load_dotenv

load_dotenv()

# Rate limit: 50 delete requests per 15-minute window (Twitter API v2)
RATE_LIMIT_DELETES = 50
RATE_LIMIT_WINDOW = 15 * 60  # 15 minutes in seconds
LOG_FILE = "deleted_tweets_log.json"
CACHE_FILE = "fetched_tweets.json"


def get_client():
    """Create and return an authenticated Twitter API v2 client."""
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")
    bearer_token = os.getenv("BEARER_TOKEN")

    missing = []
    if not api_key:
        missing.append("API_KEY")
    if not api_secret:
        missing.append("API_SECRET")
    if not access_token:
        missing.append("ACCESS_TOKEN")
    if not access_token_secret:
        missing.append("ACCESS_TOKEN_SECRET")

    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your Twitter API credentials.")
        print("Get credentials at: https://developer.x.com/en/portal/dashboard")
        sys.exit(1)

    client = tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        wait_on_rate_limit=True,
    )
    return client


def get_user_id(client):
    """Get the authenticated user's ID."""
    me = client.get_me()
    if me.data is None:
        print("ERROR: Could not fetch authenticated user. Check your credentials.")
        sys.exit(1)
    print(f"Authenticated as: @{me.data.username} (ID: {me.data.id})")
    return me.data.id


def fetch_tweets_from_api(client, user_id):
    """Fetch tweets via Twitter API v2 (limited to ~3200 most recent).
    Saves progress to cache file so credits aren't wasted on re-fetches."""
    cache_path = Path(CACHE_FILE)

    # Load cached tweets if available
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        print(f"\nLoaded {len(cached)} tweets from cache ({CACHE_FILE})")
        use_cache = input("Use cached tweets? (y/n): ").strip().lower()
        if use_cache == "y":
            return cached

    print("\nFetching tweets via API...")
    tweets = []
    pagination_token = None

    while True:
        try:
            response = client.get_users_tweets(
                id=user_id,
                max_results=100,
                pagination_token=pagination_token,
                tweet_fields=["created_at", "text"],
            )
        except Exception as e:
            print(f"\n  API error: {e}")
            if tweets:
                print(f"  Saving {len(tweets)} tweets fetched so far to {CACHE_FILE}")
                cache_path.write_text(json.dumps(tweets, indent=2, ensure_ascii=False))
            break

        if response.data:
            for tweet in response.data:
                tweets.append({
                    "id": str(tweet.id),
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                })
            print(f"  Fetched {len(tweets)} tweets so far...")
            # Save progress after each batch
            cache_path.write_text(json.dumps(tweets, indent=2, ensure_ascii=False))

        if response.meta and "next_token" in response.meta:
            pagination_token = response.meta["next_token"]
        else:
            break

    print(f"Total tweets fetched from API: {len(tweets)}")
    print(f"Saved to {CACHE_FILE}")
    return tweets


def load_tweets_from_archive(archive_path):
    """Load tweets from Twitter's data archive (tweets.js file)."""
    path = Path(archive_path)
    if not path.exists():
        print(f"ERROR: Archive file not found: {archive_path}")
        print("Download your archive from: Settings > Your Account > Download an archive of your data")
        sys.exit(1)

    print(f"\nLoading tweets from archive: {archive_path}")
    content = path.read_text(encoding="utf-8")

    # tweets.js starts with "window.YTD.tweet.part0 = " — strip that prefix
    if content.startswith("window."):
        content = content[content.index("=") + 1:].strip()
        if content.endswith(";"):
            content = content[:-1]

    data = json.loads(content)
    tweets = []
    for entry in data:
        tweet = entry.get("tweet", entry)
        tweets.append({
            "id": str(tweet["id"]) if "id" in tweet else str(tweet.get("id_str", "")),
            "text": tweet.get("full_text", tweet.get("text", "")),
            "created_at": tweet.get("created_at", None),
        })

    print(f"Total tweets loaded from archive: {len(tweets)}")
    return tweets


def filter_tweets(tweets, before_date=None, after_date=None, contains=None, exclude_contains=None):
    """Filter tweets by date and content."""
    filtered = tweets

    if before_date:
        before_dt = datetime.fromisoformat(before_date)
        original_count = len(filtered)
        new_filtered = []
        for t in filtered:
            if t["created_at"]:
                try:
                    tweet_date = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                    if tweet_date.replace(tzinfo=None) < before_dt:
                        new_filtered.append(t)
                except (ValueError, TypeError):
                    new_filtered.append(t)
            else:
                new_filtered.append(t)
        filtered = new_filtered
        print(f"  Filter --before {before_date}: {original_count} -> {len(filtered)} tweets")

    if after_date:
        after_dt = datetime.fromisoformat(after_date)
        original_count = len(filtered)
        new_filtered = []
        for t in filtered:
            if t["created_at"]:
                try:
                    tweet_date = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                    if tweet_date.replace(tzinfo=None) > after_dt:
                        new_filtered.append(t)
                except (ValueError, TypeError):
                    pass
        filtered = new_filtered
        print(f"  Filter --after {after_date}: {original_count} -> {len(filtered)} tweets")

    if contains:
        original_count = len(filtered)
        filtered = [t for t in filtered if contains.lower() in t.get("text", "").lower()]
        print(f"  Filter --contains '{contains}': {original_count} -> {len(filtered)} tweets")

    if exclude_contains:
        original_count = len(filtered)
        filtered = [t for t in filtered if exclude_contains.lower() not in t.get("text", "").lower()]
        print(f"  Filter --exclude '{exclude_contains}': {original_count} -> {len(filtered)} tweets")

    return filtered


def delete_tweets(client, tweets, dry_run=False, skip_confirm=False):
    """Delete tweets with rate limit handling and logging."""
    total = len(tweets)
    if total == 0:
        print("\nNo tweets to delete.")
        return

    if dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN — Would delete {total} tweets:")
        print(f"{'='*60}")
        for i, tweet in enumerate(tweets[:20], 1):
            text_preview = tweet["text"][:80].replace("\n", " ")
            print(f"  {i}. [{tweet.get('created_at', 'unknown date')}] {text_preview}...")
        if total > 20:
            print(f"  ... and {total - 20} more tweets")
        print(f"\nRun without --dry-run to actually delete these tweets.")
        return

    # Confirm before deletion
    print(f"\n{'='*60}")
    print(f"WARNING: About to permanently delete {total} tweets!")
    print(f"{'='*60}")
    if not skip_confirm:
        confirm = input("Type 'DELETE' to confirm: ").strip()
        if confirm != "DELETE":
            print("Aborted.")
            return
    else:
        print("Skipping confirmation (--yes flag)")


    # Load existing log and build set of already-deleted IDs
    log = []
    log_path = Path(LOG_FILE)
    already_deleted_ids = set()
    if log_path.exists():
        log = json.loads(log_path.read_text())
        already_deleted_ids = {entry["id"] for entry in log}

    # Skip already-deleted tweets
    remaining = [t for t in tweets if t["id"] not in already_deleted_ids]
    skipped = total - len(remaining)
    if skipped > 0:
        print(f"\nSkipping {skipped} already-deleted tweets (from previous runs)")
    total = len(remaining)
    if total == 0:
        print("\nAll tweets already deleted!")
        return

    deleted = 0
    failed = 0
    batch_count = 0

    print(f"\nDeleting {total} remaining tweets...")
    for i, tweet in enumerate(remaining, 1):
        tweet_id = tweet["id"]
        try:
            client.delete_tweet(int(tweet_id))
            deleted += 1
            batch_count += 1
            log.append({
                "id": tweet_id,
                "text": tweet["text"],
                "created_at": tweet.get("created_at"),
                "deleted_at": datetime.now().isoformat(),
            })
            text_preview = tweet["text"][:60].replace("\n", " ")
            print(f"  [{i}/{total}] Deleted: {text_preview}...")

        except tweepy.errors.TooManyRequests:
            print(f"\n  Rate limited. Waiting {RATE_LIMIT_WINDOW}s (15 min)...")
            log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
            time.sleep(RATE_LIMIT_WINDOW + 5)
            batch_count = 0
            # Retry this tweet
            try:
                client.delete_tweet(int(tweet_id))
                deleted += 1
                batch_count += 1
                log.append({
                    "id": tweet_id,
                    "text": tweet["text"],
                    "created_at": tweet.get("created_at"),
                    "deleted_at": datetime.now().isoformat(),
                })
            except tweepy.errors.Forbidden as e:
                if "402" in str(e) or "credits" in str(e).lower():
                    print(f"\n  No API credits! Stopping to save money.")
                    print(f"  Re-run this script after adding credits.")
                    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
                    break
                failed += 1
                print(f"  [{i}/{total}] FAILED (after retry): {e}")
            except Exception as e:
                failed += 1
                print(f"  [{i}/{total}] FAILED (after retry): {e}")

        except tweepy.errors.NotFound:
            print(f"  [{i}/{total}] Already deleted or not found: {tweet_id}")
            deleted += 1  # Count as success

        except tweepy.errors.Forbidden as e:
            error_str = str(e)
            if "402" in error_str or "credits" in error_str.lower() or "Payment Required" in error_str or "spend cap" in error_str.lower():
                print(f"\n  No API credits / spend cap reached! Stopping to save time.")
                print(f"  Re-run this script after adding credits or increasing spend cap.")
                log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
                break
            failed += 1
            print(f"  [{i}/{total}] FAILED: {e}")

        except Exception as e:
            error_str = str(e)
            if "402" in error_str or "Payment Required" in error_str or "credits" in error_str.lower() or "spend cap" in error_str.lower():
                print(f"\n  No API credits / spend cap reached! Stopping to save time.")
                print(f"  Re-run this script after adding credits or increasing spend cap.")
                log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
                break
            failed += 1
            print(f"  [{i}/{total}] FAILED: {e}")

        # Proactive rate limit pause
        if batch_count >= RATE_LIMIT_DELETES - 2:
            print(f"\n  Approaching rate limit. Pausing for {RATE_LIMIT_WINDOW}s...")
            log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
            time.sleep(RATE_LIMIT_WINDOW + 5)
            batch_count = 0

    # Save final log
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))

    print(f"\n{'='*60}")
    print(f"Done! Deleted: {deleted}, Failed: {failed}")
    print(f"Log saved to: {LOG_FILE}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Delete tweets from your Twitter/X account",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python delete_tweets.py --dry-run                    # Preview what will be deleted
  python delete_tweets.py                              # Delete all (fetched via API)
  python delete_tweets.py --archive tweets.js          # Delete all from archive
  python delete_tweets.py --before 2023-01-01          # Delete tweets before a date
  python delete_tweets.py --contains "facebook.com"    # Delete tweets with keyword
        """,
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview deletions without actually deleting")
    parser.add_argument("--archive", type=str, help="Path to tweets.js from Twitter data archive")
    parser.add_argument("--before", type=str, help="Delete tweets before this date (YYYY-MM-DD)")
    parser.add_argument("--after", type=str, help="Delete tweets after this date (YYYY-MM-DD)")
    parser.add_argument("--contains", type=str, help="Only delete tweets containing this text")
    parser.add_argument("--exclude", type=str, help="Exclude tweets containing this text")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    client = get_client()
    user_id = get_user_id(client)

    # Fetch tweets
    if args.archive:
        tweets = load_tweets_from_archive(args.archive)
    else:
        tweets = fetch_tweets_from_api(client, user_id)

    # Apply filters
    if args.before or args.after or args.contains or args.exclude:
        print("\nApplying filters...")
        tweets = filter_tweets(
            tweets,
            before_date=args.before,
            after_date=args.after,
            contains=args.contains,
            exclude_contains=args.exclude,
        )

    # Delete
    delete_tweets(client, tweets, dry_run=args.dry_run, skip_confirm=args.yes)


if __name__ == "__main__":
    main()
