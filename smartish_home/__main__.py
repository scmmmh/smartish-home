import asyncio
import logging.config

from configparser import ConfigParser

from .core import SmartishHome


async def main():
    parser = ConfigParser()
    parser.read('config.ini')
    logging.config.fileConfig(parser)

    app = SmartishHome(parser)
    await app.run()


asyncio.get_event_loop().run_until_complete(main())
