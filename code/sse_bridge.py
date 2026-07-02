import asyncio
import json
import os
import queue
import threading

import nats


_loop = None
_loop_ready = threading.Event()
_nc = None
_js = None
_start_lock = threading.Lock()
_started = False


async def _connect():
    global _nc, _js
    while _nc is None:
        try:
            _nc = await nats.connect(
                os.getenv('NATS'),
                error_cb=_on_error,
                disconnected_cb=_on_disconnected,
                reconnected_cb=_on_reconnected,
                max_reconnect_attempts=-1,
            )
        except Exception as e:
            print("sse_bridge: initial NATS connect failed, retrying: {}".format(e))
            await asyncio.sleep(2)
    _js = _nc.jetstream()
    print("sse_bridge: connected to NATS")


async def _on_error(e):
    print("sse_bridge: NATS error: {}".format(e))


async def _on_disconnected():
    print("sse_bridge: NATS disconnected")


async def _on_reconnected():
    print("sse_bridge: NATS reconnected")


def _run_loop():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.create_task(_connect())
    _loop_ready.set()
    _loop.run_forever()


def start_bridge():
    global _started
    with _start_lock:
        if _started:
            return
        t = threading.Thread(target=_run_loop, name="sse-bridge", daemon=True)
        t.start()
        _loop_ready.wait(timeout=5)
        _started = True


def subscribe(subject):
    """Subscribe to live events on a single NATS subject.

    `subject` scopes the stream server-side (e.g. events.public.<id> or
    events.private.<space_id>.<id>), so no client-side filtering is needed —
    authorization for the subject is decided by the caller before subscribing.

    Returns (queue.Queue, cancel_fn). Items pushed to the queue are dicts of
    shape {"timestamp": str, "payload": dict}. cancel_fn unsubscribes; safe to
    call from any thread, idempotent.
    """
    if _loop is None or _js is None:
        raise RuntimeError("sse_bridge not started")

    q = queue.Queue(maxsize=1000)

    async def cb(msg):
        try:
            wrapper = json.loads(msg.data.decode("utf-8"))
            inner = wrapper.get("data", {}) or {}
            try:
                q.put_nowait({
                    "timestamp": wrapper.get("timestamp"),
                    "mission_id": inner.get("mission_id"),
                    "payload": inner.get("payload"),
                })
            except queue.Full:
                print("sse_bridge: queue full for subject {}, dropping".format(subject))
        except Exception as e:
            print("sse_bridge: callback failed: {}".format(e))
        finally:
            try:
                await msg.ack()
            except Exception:
                pass

    fut = asyncio.run_coroutine_threadsafe(
        _js.subscribe(subject, cb=cb),
        _loop,
    )
    sub = fut.result(timeout=5)

    cancelled = {"v": False}

    def cancel():
        if cancelled["v"]:
            return
        cancelled["v"] = True
        try:
            asyncio.run_coroutine_threadsafe(sub.unsubscribe(), _loop).result(timeout=5)
        except Exception as e:
            print("sse_bridge: unsubscribe failed: {}".format(e))

    return q, cancel
