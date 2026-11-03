class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.commands = []

    def __getattr__(self, name):
        def queue(*args, **kwargs):
            self.commands.append((name, args, kwargs))
            return self
        return queue

    def execute(self):
        results = []
        for name, args, kwargs in self.commands:
            results.append(getattr(self.client, name)(*args, **kwargs))
        self.commands.clear()
        return results


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}
        self.expires = {}

    def set(self, key, value, ex=None, **_kwargs):
        self.values[key] = value
        if ex is not None:
            self.expires[key] = int(ex)
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        deleted = 0
        for key in keys:
            existed = key in self.values or key in self.lists
            self.values.pop(key, None)
            self.lists.pop(key, None)
            self.expires.pop(key, None)
            deleted += int(existed)
        return deleted

    def expire(self, key, seconds):
        if key not in self.values and key not in self.lists:
            return False
        self.expires[key] = int(seconds)
        return True

    def ttl(self, key):
        if key not in self.values and key not in self.lists:
            return -2
        return self.expires.get(key, -1)

    def incr(self, key):
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    def rpush(self, key, *values):
        self.lists.setdefault(key, []).extend(values)
        return len(self.lists[key])

    def ltrim(self, key, start, end):
        values = self.lists.get(key, [])
        if end == -1:
            values = values[start:]
        else:
            values = values[start:end + 1]
        self.lists[key] = values
        return True

    def lrange(self, key, start, end):
        values = self.lists.get(key, [])
        return list(values[start:] if end == -1 else values[start:end + 1])

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    def eval(self, _script, _numkeys, attempts_key, lock_key, window, max_attempts, lockout):
        if lock_key in self.values:
            return self.ttl(lock_key)
        attempts = self.incr(attempts_key)
        if attempts == 1:
            self.expire(attempts_key, window)
        if attempts >= int(max_attempts):
            self.delete(attempts_key)
            self.set(lock_key, "1", ex=lockout)
            return int(lockout)
        return 0