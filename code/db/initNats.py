import asyncio
import os
import nats
from nats.errors import TimeoutError


EVENTS_MAX_AGE_SECONDS = 15 * 60


async def main():
    nc = await nats.connect(os.getenv('NATS'))
    js = nc.jetstream()

    # `events.>` captures the split subjects: events.public.<id> and
    # events.private.<space_id>.<id>. Must stay a wildcard or publishes/reads
    # on the per-mission subjects have no bound stream and silently fail.
    try:
        await js.add_stream(
            name="events",
            subjects=["events.>"],
            max_age=EVENTS_MAX_AGE_SECONDS,
        )
    except Exception as e:
        print("add_stream events failed (may already exist): {}".format(e))

    try:
        await js.update_stream(
            name="events",
            subjects=["events.>"],
            max_age=EVENTS_MAX_AGE_SECONDS,
        )
    except Exception as e:
        print("update_stream events failed: {}".format(e))

    try:
        await js.add_stream(name="maps", subjects=["maps", "work"])
    except Exception as e:
        print("add_stream maps failed (may already exist): {}".format(e))

    await nc.close()


if __name__ == '__main__':
    asyncio.run(main())
    print("Init nats ")
