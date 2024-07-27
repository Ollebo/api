import asyncio
import code.db.natsQue as natsQue
import os
from nats.errors import TimeoutError

async def main():
    nc = await natsQue.connect(os.getenv('NATS'))

    # Create JetStream context.
    js = nc.jetstream()

    # Persist messages on 'foo's subject.
    await js.add_stream(name="events", subjects=["events"], )
    await js.add_stream(name="maps", subjects=["maps","work"] )

    # Create ordered consumer with flow control and heartbeats
    # that auto resumes on failures.
    await nc.close()




    
if __name__ == '__main__':
    asyncio.run(main())
    print("Init nats ")