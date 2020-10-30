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

    #print('Connecting')
    #async with websockets.connect('ws://10.42.8.5:8123/api/websocket') as websocket:
    #    print('Connected')
    #    while running:
    #        msg = json.loads(await websocket.recv())
    #        if msg['type'] == 'auth_required':
    #            print('Authenticating')
    #            await websocket.send(json.dumps({
    #                "type": "auth",
    #                "access_token": parser.get('HomeAssistant', 'token')
    #            }))
    #        elif msg['type'] == 'auth_ok':
    #            print('Authenticated')
    #            await send_message(websocket, 'config/area_registry/list')
    #            #await send_message(websocket, 'config/device_registry/list')
    #            #await websocket.send(json.dumps({
    #            #    'id': next(ids),
    #            #    'type': 'subscribe_events',
    #            #    'event_type': 'state_changed'
    #            #}))
    #            #await websocket.send(json.dumps({
    #            #    'id': next(ids),
    #            #    'type': 'subscribe_events',
    #            #    'event_type': 'area_registry_updated'
    #            #}))
    #            #await websocket.send(json.dumps({
    #            #    'id': next(ids),
    #            #    'type': 'subscribe_events',
    #            #    'event_type': 'device_registry_updated'
    #            #}))
    #        elif msg['type'] == 'auth_invalid':
    #            print('Authentication failed')
    #            running = False
    #        else:
    #            if messages[msg['id']] == 'config/area_registry/list':
    #                print('Area list received')
    #                del messages[msg['id']]
    #            else:
    #                print(json.dumps(msg, indent=2))


asyncio.get_event_loop().run_until_complete(main())
