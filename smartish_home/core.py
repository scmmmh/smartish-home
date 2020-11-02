import json
import logging
import websockets

from asyncio import gather
from asyncio_mqtt import Client
from configparser import ConfigParser

from .room import RoomController
from .util import id_seq


LOGGER = logging.getLogger('smartish_home.websocket')


class SmartishHome():

    def __init__(self, config: ConfigParser):
        self._config = config
        LOGGER.info('Starting')

    async def run(self):
        LOGGER.info('Connecting')
        async with websockets.connect(self._config.get('HomeAssistant', 'websocket')) as websocket:
            LOGGER.debug('Websocket connected')
            client = Client(self._config.get('MQTT', 'host'))
            client._client.username_pw_set(self._config.get('MQTT', 'username'), self._config.get('MQTT', 'password'))
            async with client as mqtt_session:
                LOGGER.debug('MQTT connected')
                ws_handler = WebsocketHandler(self._config, websocket)
                await ws_handler.run()


class WebsocketHandler():

    def __init__(self, config: ConfigParser, websocket):
        self._config = config
        self._ids = id_seq()
        self._messages = {}
        self._websocket = websocket
        self._rooms = []

    async def run(self):
        while True:
            msg = json.loads(await self._websocket.recv())
            if msg['type'] == 'auth_required':
                LOGGER.debug('Authenticating')
                await self._websocket.send(json.dumps({
                    "type": "auth",
                    "access_token": self._config.get('HomeAssistant', 'token')
                }))
            elif msg['type'] == 'auth_ok':
                LOGGER.debug('Authenticated')
                await self.send_message('config/area_registry/list')
            #await websocket.send(json.dumps({
            #    'id': next(ids),
            #    'type': 'subscribe_events',
            #    'event_type': 'state_changed'
            #}))
            #await websocket.send(json.dumps({
            #    'id': next(ids),
            #    'type': 'subscribe_events',
            #    'event_type': 'area_registry_updated'
            #}))
            #await websocket.send(json.dumps({
            #    'id': next(ids),
            #    'type': 'subscribe_events',
            #    'event_type': 'device_registry_updated'
            #}))
            elif msg['type'] == 'auth_invalid':
                LOGGER.debug('Authentication failed')
                break
            else:
                if msg['id'] in self._messages:
                    msg_type = self._messages[msg['id']]
                    if msg_type == 'config/area_registry/list':
                        self._setup_rooms(msg['result'])
                        del self._messages[msg['id']]
                        await self.send_message('config/device_registry/list')
                    elif msg_type == 'config/device_registry/list':
                        await gather(*[room.add_devices(msg['result']) for room in self._rooms])
                        del self._messages[msg['id']]
                        await self.send_message('config/entity_registry/list')
                    elif msg_type == 'config/entity_registry/list':
                        await gather(*[room.add_entities(msg['result']) for room in self._rooms])
                        del self._messages[msg['id']]
                        await self.send_message('get_states')
                    elif msg_type == 'get_states':
                        await gather(*[room.update_states(msg['result']) for room in self._rooms])
                        del self._messages[msg['id']]

    def _setup_rooms(self, rooms):
        self._rooms = [RoomController(self, room) for room in rooms]

    async def send_message(self, message_type, payload=None):
        identifier = next(self._ids)
        msg = {
            'id': identifier,
            'type': message_type,
        }
        if payload:
            msg.update(payload)
        await self._websocket.send(json.dumps(msg))
        self._messages[identifier] = message_type
