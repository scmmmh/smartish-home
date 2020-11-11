import asyncio
import logging.config
import signal

from configparser import ConfigParser

from .core import SmartishHome


async def shutdown(app):
    await app.shutdown()
    await asyncio.sleep(5)
    await asyncio.gather(*[task.cancel() for task in asyncio.all_tasks() if task is not asyncio.current_task()])


async def main():
    parser = ConfigParser()
    parser.read('config.ini')
    logging.config.fileConfig(parser)

    app = SmartishHome(parser)

    def signal_handler():
        asyncio.create_task(app.shutdown())

    for signl in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        asyncio.get_event_loop().add_signal_handler(signl, signal_handler)

    await asyncio.wait((asyncio.create_task(app.run()),))


asyncio.get_event_loop().run_until_complete(main())
