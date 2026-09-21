import json
import re
from openai import OpenAI
from src.config import Config
from src.prompt_loader import PromptLoader
import logging

logger = logging.getLogger(__name__)

# Frequent German function words that carry no topical signal. Kept short on
# purpose: anything not listed here is simply weighted by its length below.
STOPWORDS = {
    'aber', 'als', 'auch', 'auf', 'aus', 'bei', 'beim', 'dass', 'dem', 'den',
    'der', 'des', 'die', 'diese', 'dieser', 'dieses', 'durch', 'ein', 'eine',
    'einem', 'einen', 'einer', 'eines', 'fuer', 'gegen', 'haben', 'hat',
    'ihre', 'ihren', 'immer', 'ist', 'kann', 'mehr', 'mit', 'nach', 'nicht',
    'noch', 'oder', 'ohne', 'schon', 'sein', 'seine', 'seinen', 'sich', 'sie',
    'sind', 'soll', 'sollen', 'ueber', 'und', 'uns', 'unter', 'vom', 'von',
    'vor', 'war', 'was', 'wegen', 'weil', 'werden', 'wie', 'wir', 'wird',
    'wurde', 'wurden', 'zum', 'zur',
}

UMLAUTS = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'})
# Three characters, so party and country acronyms (SPD, CDU, EU, USA) count -
# they are among the most story-specific tokens in a German headline.
TOKEN_PATTERN = re.compile(r'[a-z0-9]{3,}')
SLUG_PATTERN = re.compile(r'[^a-z0-9]+')


class NewsRanker:
    """Ranks news articles by importance and picks one article per topic"""

    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        self.temperature = Config.OPENAI_TEMPERATURE
        self.max_tokens = Config.OPENAI_MAX_TOKENS
        # sophoraId -> {'topic': slug or None, 'status': 'selected'|'dropped'}
        self.last_topic_map = {}

    def rank_articles(self, articles):
        """
        Rank articles by importance and return the top N, each on a different topic

        Args:
            articles: List of article dictionaries

        Returns:
            list: Up to NEWS_COUNT most important articles, one per topic
        """
        self.last_topic_map = {}

        if not articles:
            logger.warning("No articles to rank")
            return []

        # Only skip the LLM when there is nothing to choose between. Anything
        # above one article still needs topic deduplication, even a batch
        # smaller than NEWS_COUNT - those can all be the same story.
        if len(articles) <= 1:
            logger.info(f"Only {len(articles)} article(s), returning all")
            return articles[:Config.NEWS_COUNT]

        try:
            # Prepare articles for ranking
            articles_for_prompt = []
            for idx, article in enumerate(articles):
                articles_for_prompt.append({
                    'id': idx,
                    'title': article.get('title', ''),
                    'date': article.get('date', ''),
                    'topline': article.get('topline', ''),
                    'firstSentence': article.get('firstSentence', '')
                })

            prompt = self._build_ranking_prompt(articles_for_prompt)

            logger.info(f"Sending {len(articles)} articles to OpenAI for ranking")

            system_prompt, _, max_tokens = PromptLoader.get_ranking_prompts()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_completion_tokens=max_tokens
            )

            result_text = response.choices[0].message.content.strip()
            logger.debug(f"OpenAI ranking response: {result_text}")

            # Parse JSON response into [{'id': int, 'topic': str|None}, ...]
            candidates = self._parse_ranking_response(result_text)

            # Pick the top N, at most one per topic
            top_articles = self._select_diverse(articles, candidates)

            topics = [a.get('topic') for a in top_articles]
            logger.info(f"Selected top {len(top_articles)} articles, topics: {topics}")
            return top_articles

        except Exception as e:
            # Loud on purpose: a silent fallback here once hid the fact that
            # ranking was not running at all for weeks.
            logger.error(
                f"Ranking failed - NO ranking and NO topic filtering applied: {e}",
                exc_info=True
            )
            logger.error(f"Falling back to first {Config.NEWS_COUNT} articles in feed order")
            return articles[:Config.NEWS_COUNT]

    def _select_diverse(self, articles, candidates):
        """
        Walk the ranked candidates and keep at most one article per topic

        Two filters run in sequence because they fail in opposite directions:
        the topic slug catches same-event articles that share no vocabulary,
        while the word-overlap backstop catches the same event labelled with
        two different slugs.

        Args:
            articles: Full list of article dictionaries (candidate ids index it)
            candidates: List of {'id': int, 'topic': str|None} in rank order

        Returns:
            list: Up to NEWS_COUNT articles, each tagged with its 'topic'
        """
        selected = []
        seen_topics = set()
        deferred = []
        used_ids = set()

        for entry in candidates:
            article_id = entry.get('id')
            if not (0 <= article_id < len(articles)):
                logger.warning(f"Ranking returned out-of-range article id: {article_id}")
                continue
            if article_id in used_ids:
                continue
            used_ids.add(article_id)

            article = articles[article_id]
            sophora_id = article.get('sophoraId')
            topic = self._normalize_topic(entry.get('topic'))
            # A missing slug must never *remove* articles, so give it a key that
            # cannot collide and let the backstop below do the work instead.
            key = topic or f"__untagged-{sophora_id}"
            self.last_topic_map[sophora_id] = {'topic': topic, 'status': 'dropped'}

            if key in seen_topics:
                logger.info(f"Dropped (duplicate topic '{key}'): {article.get('title')}")
                deferred.append((article, key))
                continue

            # Compare only against already-selected articles: comparing against
            # deferred ones would let a single rejection cascade.
            similarity = 0.0
            closest = None
            for chosen in selected:
                score = self._similarity(article, chosen)
                if score > similarity:
                    similarity, closest = score, chosen

            if similarity >= Config.TOPIC_SIMILARITY_THRESHOLD:
                logger.info(
                    f"Dropped (similarity {similarity:.2f} to "
                    f"'{closest.get('title')}'): {article.get('title')}"
                )
                deferred.append((article, key))
                continue

            article['topic'] = key
            seen_topics.add(key)
            selected.append(article)
            self.last_topic_map[sophora_id]['status'] = 'selected'

            if len(selected) >= Config.NEWS_COUNT:
                break

        # Never ship a short digest silently: on a day where everything is one
        # story, fill the remaining slots with the best rejected candidates.
        if len(selected) < Config.NEWS_COUNT and deferred:
            missing = Config.NEWS_COUNT - len(selected)
            logger.warning(
                f"Only {len(selected)} distinct topic(s) among the candidates - "
                f"filling up to {missing} slot(s) with duplicate-topic articles"
            )
            for article, key in deferred[:missing]:
                article['topic'] = key
                selected.append(article)
                sophora_id = article.get('sophoraId')
                if sophora_id in self.last_topic_map:
                    self.last_topic_map[sophora_id]['status'] = 'selected'

        return selected

    @staticmethod
    def _normalize_topic(topic):
        """Reduce a topic slug to a canonical form so near-misses still match"""
        if not isinstance(topic, str):
            return None

        slug = topic.strip().lower().translate(UMLAUTS)
        slug = SLUG_PATTERN.sub('-', slug).strip('-')

        return slug or None

    @staticmethod
    def _tokens(article):
        """
        Significant words of an article's headline

        Deliberately headline-only. The 'topline' field holds a category
        label - for regional pieces it is just the Bundesland - so including
        it made every unrelated story from the same state look similar
        ("Hundeangriff in Schoenberg" scored 0.50 against a state election
        story purely on a shared "Mecklenburg-Vorpommern" topline).
        """
        text = article.get('title', '').lower().translate(UMLAUTS)

        return {w for w in TOKEN_PATTERN.findall(text) if w not in STOPWORDS}

    @classmethod
    def _similarity(cls, first, second):
        """
        Length-weighted word overlap between two articles, from 0.0 to 1.0

        Each word counts for its own length rather than 1, because in German
        headlines the long compound noun ("Bundestagswahl", "Tarifstreit") is
        what identifies the story, while sharing "klar" or "mehr" means
        nothing. Unweighted counting scores two articles on the same election
        at only 0.33, which is indistinguishable from noise.

        Overlap rather than Jaccard because headlines vary a lot in length,
        and Jaccard penalises a short headline against a long one even when
        the short one is fully contained in it.
        """
        a = cls._tokens(first)
        b = cls._tokens(second)

        # A single significant word is not enough to judge. Two is: terse
        # headlines like "Der Bund nach den Wahlen" are exactly the ones that
        # recur during a big story, and excluding them made every such
        # headline immune to this check.
        if len(a) < 2 or len(b) < 2:
            return 0.0

        weight_a = sum(len(w) for w in a)
        weight_b = sum(len(w) for w in b)
        shared = sum(len(w) for w in a & b)

        return shared / min(weight_a, weight_b)

    def _build_ranking_prompt(self, articles):
        """Build the ranking prompt in German"""
        articles_text = json.dumps(articles, ensure_ascii=False, indent=2)

        # Never ask for more candidates than exist, but always enough to fill
        # the digest even if the model returns exactly the requested number.
        candidate_count = max(
            Config.NEWS_COUNT,
            min(Config.RANKING_CANDIDATE_COUNT, len(articles))
        )

        _, user_template, _ = PromptLoader.get_ranking_prompts()

        prompt = user_template.format(
            candidate_count=candidate_count,
            articles_json=articles_text
        )

        return prompt

    def _parse_ranking_response(self, response_text):
        """
        Parse the ranking response from OpenAI

        Returns:
            list: [{'id': int, 'topic': str|None}, ...] in rank order
        """
        try:
            # Try to find JSON array in response
            start = response_text.find('[')
            end = response_text.rfind(']') + 1

            if start == -1 or end <= start:
                raise ValueError("No JSON array found in response")

            raw_entries = json.loads(response_text[start:end])

            candidates = []
            for entry in raw_entries:
                if isinstance(entry, dict):
                    article_id = entry.get('id')
                    topic = entry.get('topic')
                elif isinstance(entry, int) and not isinstance(entry, bool):
                    # Tolerate the older bare-id format
                    article_id, topic = entry, None
                else:
                    logger.warning(f"Skipping unrecognised ranking entry: {entry!r}")
                    continue

                if isinstance(article_id, str) and article_id.isdigit():
                    article_id = int(article_id)

                if not isinstance(article_id, int) or isinstance(article_id, bool):
                    logger.warning(f"Skipping ranking entry without usable id: {entry!r}")
                    continue

                candidates.append({'id': article_id, 'topic': topic})

            if not candidates:
                raise ValueError("No usable entries in ranking response")

            return candidates

        except Exception as e:
            logger.error(f"Error parsing ranking response: {e}")
            # Same shape as the success path so the caller still works
            return [{'id': i, 'topic': None} for i in range(Config.NEWS_COUNT)]
