import json
import logging
import websockets

from configparser import ConfigParser

from .room import RoomController
from .util import id_seq


LOGGER = logging.getLogger('smartish_home.websocket')


class HAWebsocket():

    def __init__(self, config: ConfigParser):
        self._config = config
        self._ids = id_seq()
        self._messages = {}
        self._websocket = None
        self._rooms = []

    async def run(self):
        LOGGER.info('Connecting')
        async with websockets.connect(self._config.get('HomeAssistant', 'websocket')) as websocket:
            self._websocket = websocket
            LOGGER.debug('Connected')
            while True:
                msg = json.loads(await websocket.recv())
                if msg['type'] == 'auth_required':
                    LOGGER.debug('Authenticating')
                    await websocket.send(json.dumps({
                        "type": "auth",
                        "access_token": self._config.get('HomeAssistant', 'token')
                    }))
                elif msg['type'] == 'auth_ok':
                    LOGGER.debug('Authenticated')
                    await self._send_message('config/area_registry/list')
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
                            await self._send_message('config/device_registry/list')
                        elif msg_type == 'config/device_registry/list':
                            for room in self._rooms:
                                room.add_devices(msg['result'])
                            del self._messages[msg['id']]
                            await self._send_message('config/entity_registry/list')
                        elif msg_type == 'config/entity_registry/list':
                            for room in self._rooms:
                                room.add_entities(msg['result'])
                            del self._messages[msg['id']]
                            await self._send_message('get_states')
                        elif msg_type == 'get_states':
                            for room in self._rooms:
                                room.update_states(msg['result'])
                            del self._messages[msg['id']]

    def _setup_rooms(self, rooms):
        self._rooms = [RoomController(room) for room in rooms]

    async def _send_message(self, message_type, payload=None):
        identifier = next(self._ids)
        msg = {
            'id': identifier,
            'type': message_type,
        }
        if payload:
            msg.update(payload)
        await self._websocket.send(json.dumps(msg))
        self._messages[identifier] = message_type
