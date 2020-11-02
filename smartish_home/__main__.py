import asyncio
import logging
import logging.config

from configparser import ConfigParser

from .websocket import HAWebsocket


LOGGER = logging.getLogger('smartish_home')


async def main():
    parser = ConfigParser()
    parser.read('config.ini')
    logging.config.fileConfig(parser)

    LOGGER.info('Starting up')

    ha_websocket = HAWebsocket(parser)
    await ha_websocket.run()


asyncio.get_event_loop().run_until_complete(main())
