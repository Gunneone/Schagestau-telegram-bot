import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from src.config import Config
import logging

logger = logging.getLogger(__name__)

# Fields the rest of the pipeline reads off an article. A stored record has to
# stand in for a live one in the ranker, the summarizer and format_digest.
ARTICLE_FIELDS = (
    'sophoraId', 'title', 'date', 'topline', 'firstSentence',
    'shareURL', 'detailsweb',
)


class Storage:
    """Persists the last fetch timestamp and the carry-over article pool"""

    # ------------------------------------------------------------------
    # Last fetch timestamp
    # ------------------------------------------------------------------

    @staticmethod
    def get_last_fetch_time():
        """Get the last fetch timestamp"""
        if not os.path.exists(Config.LAST_FETCH_FILE):
            logger.info("No previous fetch timestamp found")
            return None
        
        try:
            with open(Config.LAST_FETCH_FILE, 'r') as f:
                data = json.load(f)
                timestamp_str = data.get('last_fetch')
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    logger.info(f"Last fetch was at: {timestamp}")
                    return timestamp
        except Exception as e:
            logger.error(f"Error reading last fetch time: {e}")
        
        return None
    
    @staticmethod
    def save_last_fetch_time(timestamp):
        """Save the last fetch timestamp"""
        try:
            with open(Config.LAST_FETCH_FILE, 'w') as f:
                json.dump({
                    'last_fetch': timestamp.isoformat()
                }, f)
            logger.info(f"Updated last fetch timestamp to: {timestamp}")
        except Exception as e:
            logger.error(f"Error saving last fetch time: {e}")

    # ------------------------------------------------------------------
    # Carry-over pool
    # ------------------------------------------------------------------

    @staticmethod
    def remember_articles(articles, content_texts):
        """
        Record articles seen in this run so they can be carried over later

        Articles already posted are never re-added, so a --force re-run cannot
        resurrect news the channel has already had.

        Args:
            articles: List of article dictionaries
            content_texts: Extracted article texts, parallel to articles
        """
        if not articles:
            return

        store = Storage._load_pool()
        known = {entry['article'].get('sophoraId') for entry in store['pool']}
        now = Storage._now().isoformat()
        added = 0

        for article, content_text in zip(articles, content_texts):
            sophora_id = article.get('sophoraId')
            if not sophora_id or sophora_id in known or sophora_id in store['posted']:
                continue

            store['pool'].append({
                'first_seen': now,
                'content_text': content_text or '',
                'article': {k: article[k] for k in ARTICLE_FIELDS if k in article},
            })
            known.add(sophora_id)
            added += 1

        if added:
            logger.info(f"Remembered {added} new article(s) for possible carry-over")
        Storage._save_pool(store)

    @staticmethod
    def remember_topics(topic_map):
        """
        Annotate pooled articles with the topic the ranker gave them

        Topics are only known after ranking, so this runs as a second pass.
        Without it a carried-over article has no topic and the "already posted
        this story" guard in get_carryover_articles can never fire.

        Args:
            topic_map: NewsRanker.last_topic_map, {sophoraId: {'topic': slug}}
        """
        if not topic_map:
            return

        store = Storage._load_pool()
        updated = 0

        for entry in store['pool']:
            sophora_id = entry['article'].get('sophoraId')
            info = topic_map.get(sophora_id) or {}
            topic = info.get('topic')
            if topic and entry.get('topic') != topic:
                entry['topic'] = topic
                updated += 1

        if updated:
            logger.debug(f"Recorded topics for {updated} pooled article(s)")
            Storage._save_pool(store)

    @staticmethod
    def get_carryover_articles(exclude_ids=None, exclude_topics=None):
        """
        Unposted articles from earlier runs, newest first

        Args:
            exclude_ids: sophoraIds already present in this run's fresh batch
            exclude_topics: Topic slugs posted recently, whose articles should
                            not resurface (None disables the check)

        Returns:
            tuple: (articles, content_texts) as parallel lists
        """
        exclude_ids = exclude_ids or set()
        store = Storage._load_pool()

        # Imported here to avoid a circular import at module load
        from src.ranker import NewsRanker

        normalised_topics = set()
        if exclude_topics:
            for topic in exclude_topics:
                slug = NewsRanker._normalize_topic(topic)
                if slug:
                    normalised_topics.add(slug)

        articles, content_texts = [], []
        for entry in sorted(store['pool'], key=lambda e: e['article'].get('date', ''), reverse=True):
            article = dict(entry['article'])
            sophora_id = article.get('sophoraId')

            if sophora_id in exclude_ids or sophora_id in store['posted']:
                continue

            if normalised_topics:
                topic = NewsRanker._normalize_topic(entry.get('topic'))
                if topic and topic in normalised_topics:
                    logger.info(
                        f"Carry-over skipped (topic '{topic}' already posted): "
                        f"{article.get('title')}"
                    )
                    continue

            article['carried_over'] = True
            articles.append(article)
            content_texts.append(entry.get('content_text', ''))

        return articles, content_texts

    @staticmethod
    def mark_posted(articles):
        """
        Record that these articles went out, and drop them from the pool

        Args:
            articles: Posted article dictionaries, each optionally carrying the
                      'topic' slug the ranker assigned
        """
        if not articles:
            return

        store = Storage._load_pool()
        now = Storage._now().isoformat()

        for article in articles:
            sophora_id = article.get('sophoraId')
            if not sophora_id:
                continue
            store['posted'][sophora_id] = {
                'posted_at': now,
                'topic': article.get('topic'),
            }

        posted_ids = {a.get('sophoraId') for a in articles}
        store['pool'] = [e for e in store['pool']
                         if e['article'].get('sophoraId') not in posted_ids]

        logger.info(f"Marked {len(posted_ids)} article(s) as posted")
        Storage._save_pool(store)

    @staticmethod
    def get_recent_posted_topics():
        """Topic slugs posted within the carry-over window"""
        store = Storage._load_pool()
        cutoff = Storage._now() - timedelta(hours=Config.CARRYOVER_MAX_AGE_HOURS)

        topics = set()
        for record in store['posted'].values():
            topic = record.get('topic')
            if not topic:
                continue
            posted_at = Storage._parse(record.get('posted_at'))
            if posted_at and posted_at >= cutoff:
                topics.add(topic)

        return topics

    # ------------------------------------------------------------------
    # Pool file helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse(timestamp_str):
        """Parse a stored ISO timestamp, always returning it timezone aware"""
        if not timestamp_str:
            return None
        try:
            parsed = datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _load_pool():
        """Read the pool file and drop anything past its retention window"""
        store = {'pool': [], 'posted': {}}

        if os.path.exists(Config.ARTICLE_POOL_FILE):
            try:
                with open(Config.ARTICLE_POOL_FILE, 'r') as f:
                    data = json.load(f)
                if isinstance(data.get('pool'), list):
                    store['pool'] = [e for e in data['pool']
                                     if isinstance(e, dict) and isinstance(e.get('article'), dict)]
                if isinstance(data.get('posted'), dict):
                    store['posted'] = data['posted']
            except Exception as e:
                # A corrupt pool must never stop the digest - start over
                logger.error(f"Error reading article pool, starting empty: {e}")
                return {'pool': [], 'posted': {}}

        now = Storage._now()
        pool_cutoff = now - timedelta(hours=Config.CARRYOVER_MAX_AGE_HOURS)
        posted_cutoff = now - timedelta(hours=Config.POSTED_RETENTION_HOURS)

        kept_pool = []
        for entry in store['pool']:
            first_seen = Storage._parse(entry.get('first_seen'))
            if first_seen is None or first_seen >= pool_cutoff:
                kept_pool.append(entry)

        kept_posted = {}
        for sophora_id, record in store['posted'].items():
            if not isinstance(record, dict):
                continue
            posted_at = Storage._parse(record.get('posted_at'))
            if posted_at is None or posted_at >= posted_cutoff:
                kept_posted[sophora_id] = record

        expired = len(store['pool']) - len(kept_pool)
        if expired:
            logger.info(f"Expired {expired} article(s) from the carry-over pool")

        return {'pool': kept_pool, 'posted': kept_posted}

    @staticmethod
    def _save_pool(store):
        """
        Write the pool atomically

        The pool is rewritten on every run and is far larger than the fetch
        timestamp, so a half-written file must never be left behind.
        """
        try:
            directory = os.path.dirname(os.path.abspath(Config.ARTICLE_POOL_FILE))
            os.makedirs(directory, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(dir=directory, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(store, f, ensure_ascii=False)
                os.replace(temp_path, Config.ARTICLE_POOL_FILE)
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

            logger.debug(
                f"Saved article pool: {len(store['pool'])} pending, "
                f"{len(store['posted'])} posted"
            )
        except Exception as e:
            logger.error(f"Error saving article pool: {e}")
