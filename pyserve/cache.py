import os
import queue
import threading
from typing import Dict, List, Optional

from .utils.logger import logger

DEFAULT_THREAD_DIVISOR = 4

def default_thread_count(divisor: int = DEFAULT_THREAD_DIVISOR) -> int:
    """A quarter of the machine's threads, never fewer than one."""
    return max(1, (os.cpu_count() or divisor) // divisor)

class DirectoryCache:

    """Directory listings kept in memory and warmed in the background.

    Nothing is cached while the first listing is being served. Once that first
    request is done the cache walks the whole tree on a small pool of threads,
    so the deeper folders of a large filesystem are already in memory by the
    time anyone clicks into them. Every page load resets the cache and warms it
    again, so a listing is never served from a stale entry.

    Attributes:
        enabled: When False every lookup misses and nothing is ever warmed
        threads: Size of the warming pool, a quarter of the CPU threads by default
        max_dirs: Stop warming after this many directories, 0 meaning no limit
    """

    def __init__(self, enabled: bool = True, threads: int = 0, max_dirs: int = 0):
        self.enabled = enabled
        self.threads = threads if threads and threads > 0 else default_thread_count()
        self.max_dirs = max(0, max_dirs)
        self._entries: Dict[str, List[Dict]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._armed = True
        self._queued = False
        self._warming = False
        self._complete = False
        self._truncated = False
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __repr__(self) -> str:
        return f"DirectoryCache({len(self)} dirs, threads={self.threads}, complete={self.complete})"

    @property
    def complete(self) -> bool:
        """True when the whole tree has been walked and nothing invalidated it since."""
        with self._lock:
            return self._complete

    @property
    def warming(self) -> bool:
        """True while the background walk is still running."""
        with self._lock:
            return self._warming

    @property
    def pending(self) -> bool:
        """True when a warm is owed but has not started yet."""
        with self._lock:
            return self._armed or self._queued

    def stats(self) -> Dict:
        """Counters worth looking at when a tree is slow."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "dirs": len(self._entries),
                "threads": self.threads,
                "complete": self._complete,
                "warming": self._warming,
                "truncated": self._truncated,
                "hits": self.hits,
                "misses": self.misses,
            }

    def get(self, key: str) -> Optional[List[Dict]]:
        """Returns a cached listing, or None on a miss."""
        if not self.enabled:
            return None
        with self._lock:
            entries = self._entries.get(key)
            if entries is None:
                self.misses += 1
                return None
            self.hits += 1
            return entries

    def put(self, key: str, entries: List[Dict]) -> None:
        """Stores a listing."""
        if not self.enabled:
            return
        with self._lock:
            if self.max_dirs and key not in self._entries and len(self._entries) >= self.max_dirs:
                self._truncated = True
                return
            self._entries[key] = entries

    def snapshot(self) -> Dict[str, List[Dict]]:
        """A shallow copy of every cached listing, safe to iterate."""
        with self._lock:
            return dict(self._entries)

    def invalidate(self, key: str) -> None:
        """Drops one directory."""
        with self._lock:
            self._entries.pop(key, None)

    def drop_subtree(self, key: str) -> None:
        """Drops a directory and everything below it, and marks the cache incomplete."""
        key = (key or "").strip("/")
        with self._lock:
            if not key:
                self._entries.clear()
            else:
                prefix = key + "/"
                for cached in [k for k in self._entries if k == key or k.startswith(prefix)]:
                    self._entries.pop(cached, None)
            self._complete = False

    def clear(self) -> None:
        """Empties the cache without touching the warming state."""
        with self._lock:
            self._entries.clear()
            self._complete = False

    def reset(self) -> None:
        """Empties the cache and arms a fresh warm for the next listing."""
        self._stop.set()
        self.clear()
        with self._lock:
            self._armed = True
            self._queued = False
            self.hits = 0
            self.misses = 0

    def stop(self) -> None:
        """Asks the warming pool to wind down."""
        self._stop.set()
        with self._lock:
            self._armed = False
            self._queued = False

    def warm(self, store) -> bool:
        """Starts the background walk, once per reset, when a listing has been served."""
        with self._lock:
            if not self.enabled:
                return False
            if self._armed:
                self._armed = False
                self._queued = True
            if not self._queued or self._warming:
                return False
            self._queued = False
            self._warming = True
            self._truncated = False
        self._stop.clear()
        threading.Thread(target=self._warm, args=(store,), daemon=True).start()
        return True

    def _warm(self, store) -> None:
        work: "queue.Queue" = queue.Queue()
        work.put("")
        workers = [
            threading.Thread(target=self._worker, args=(store, work), daemon=True)
            for _ in range(self.threads)
        ]
        for worker in workers:
            worker.start()
        work.join()
        for _ in workers:
            work.put(None)

        stopped = self._stop.is_set()
        with self._lock:
            self._warming = False
            self._complete = not stopped and not self._truncated
            queued = self._queued
            cached = len(self._entries)
        if not stopped:
            logger.debug(f"Cache warmed {cached} directories on {self.threads} thread(s)")
        if queued:
            self.warm(store)

    def _worker(self, store, work: "queue.Queue") -> None:
        while True:
            rel_path = work.get()
            try:
                if rel_path is None:
                    return
                if self._stop.is_set():
                    continue
                entries = store.scan(rel_path)
                if entries is None or self._stop.is_set():
                    continue
                self.put(rel_path, entries)
                if self.max_dirs and len(self) >= self.max_dirs:
                    with self._lock:
                        self._truncated = True
                    continue
                for entry in entries:
                    if entry["type"] == "dir":
                        child = f"{rel_path}/{entry['name']}" if rel_path else entry["name"]
                        work.put(child)
            except OSError:
                continue
            finally:
                work.task_done()
