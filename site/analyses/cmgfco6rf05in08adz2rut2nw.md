## 题目本质

**Design Twitter (LLD version)** —— Low Level Design (OOP)：实现 Twitter core feature 的 class diagram + interface。区别于 System Design 的架构，重点是**类设计 + 模式 + extensibility**。

## 核心实体

```python
class User:
    user_id: UUID
    name: str
    followers: set[User]    # who follows me
    following: set[User]    # who I follow
    tweets: list[Tweet]
    feed: 'NewsFeed'

class Tweet:
    tweet_id: UUID
    author: User
    text: str
    media: list[Media]
    created_at: datetime
    likes: set[User]
    retweets: set['Tweet']     # retweeted_by tweets
    parent: 'Tweet' | None     # for replies / retweets

class NewsFeed:
    user: User
    cached_tweets: list[Tweet]   # paginated

class TwitterService:
    users: dict[UUID, User]
    tweets: dict[UUID, Tweet]

    def post_tweet(self, user_id, text, media) -> Tweet
    def follow(self, follower, followee)
    def unfollow(self, follower, followee)
    def like(self, user, tweet)
    def get_feed(self, user_id, limit) -> list[Tweet]
    def search(self, query) -> list[Tweet]
```

## 设计 patterns

### 1. Strategy: Feed generation

```python
class FeedStrategy(ABC):
    @abstractmethod
    def get_feed(user, limit) -> list[Tweet]: ...

class PullModelStrategy(FeedStrategy):
    """Query 所有 followed users' tweets, sort, top-K"""
    def get_feed(user, limit):
        all_tweets = []
        for followed in user.following:
            all_tweets.extend(followed.tweets[-100:])
        return sorted(all_tweets, key=lambda t: -t.created_at.timestamp())[:limit]

class PushModelStrategy(FeedStrategy):
    """Each tweet upon post fan-out to followers' feed cache"""
    def get_feed(user, limit):
        return user.feed.cached_tweets[:limit]

class HybridStrategy(FeedStrategy):
    """Push for normal user, pull for celebrities (avoid fan-out爆)"""
    def get_feed(user, limit):
        merged = list(user.feed.cached_tweets)
        for celeb in user.following_celebs:
            merged.extend(celeb.tweets[-20:])
        return sorted(merged, key=...)[:limit]
```

### 2. Observer: Notification

User likes tweet → tweet author receives notification。Observer pattern：

```python
class TweetObserver(ABC):
    def on_like(tweet, user): ...
    def on_retweet(tweet, user): ...

class NotificationObserver(TweetObserver):
    def on_like(tweet, user):
        notify(tweet.author, f"{user.name} liked your tweet")
```

### 3. Decorator / Composite: Media

Tweet can have text + image + video. Composite media:

```python
class Media(ABC): ...
class Image(Media): ...
class Video(Media): ...
class Gif(Media): ...
```

### 4. Factory: Tweet creation

```python
class TweetFactory:
    @staticmethod
    def create(text, author, media=None, parent=None) -> Tweet:
        t = Tweet(uuid4(), author, text, media or [], now(), set(), set(), parent)
        # validation
        if len(text) > 280:
            raise ValueError
        # extract mentions, hashtags
        for mention in extract_mentions(text):
            notify(mention)
        return t
```

## Code 关键

```python
class TwitterService:
    def __init__(self, feed_strategy: FeedStrategy):
        self.users: dict[UUID, User] = {}
        self.tweets: dict[UUID, Tweet] = {}
        self.feed_strategy = feed_strategy
        self.observers: list[TweetObserver] = []

    def post_tweet(self, user_id: UUID, text: str, media: list[Media] = None):
        user = self.users[user_id]
        tweet = TweetFactory.create(text, user, media)
        self.tweets[tweet.tweet_id] = tweet
        user.tweets.append(tweet)
        # Push model: fan-out
        if isinstance(self.feed_strategy, PushModelStrategy):
            for follower in user.followers:
                follower.feed.cached_tweets.insert(0, tweet)
                if len(follower.feed.cached_tweets) > 100:
                    follower.feed.cached_tweets.pop()
        return tweet

    def follow(self, follower_id, followee_id):
        f = self.users[follower_id]
        ft = self.users[followee_id]
        f.following.add(ft)
        ft.followers.add(f)

    def get_feed(self, user_id, limit=20):
        return self.feed_strategy.get_feed(self.users[user_id], limit)
```

## 关键设计点

### 1. Pull vs Push vs Hybrid

参考 System Design Twitter。**Strategy pattern** 让 service 切换。

### 2. 数据集中 vs 分布

LLD focus on objects + relationships，不深入 storage。但要注意 **不要把所有 tweet 放 User 类里** —— 用单独 dict + reference。

### 3. Lazy loading

Tweet detail（media URL, likes count）lazy load。Don't preload everything。

## 易错点

> [!pitfall]
> ❌ User 类 own all tweets → memory model 错；
> ❌ Followers / Following 互相 reference → cycle，hard for serialization。用 ID 而非 object reference；
> ❌ 不用 Strategy → feed algorithm hardcode；
> ❌ 不用 Observer → coupling tight；
> ❌ Composite media 不抽象 → 新 media type 改 Tweet 类。

> [!key]
> Twitter LLD = **User / Tweet / NewsFeed entities + Strategy (feed) + Observer (notif) + Factory (validation)**。展示 design pattern 熟练度。

> [!followup]
> "如何实现 search？" → ES integration + tweet indexing；"Reply tree 深嵌套？" → parent_id pointer + Tree traversal；"Media moderation？" → 加 moderation service queue，async processing；"如何 unit test？" → mock observers + inject strategy。
