import json
import logging
import os
import websockets

from asyncio import gather, wait_for, TimeoutError
from asyncio_mqtt import Client
from configparser import ConfigParser

from .room import RoomController
from .util import id_seq


LOGGER = logging.getLogger('smartish_home.websocket')


class SmartishHome():

    def __init__(self, config: ConfigParser):
        self._config = config
        self._ws_handler = None
        LOGGER.info('Starting')

    async def run(self):
        LOGGER.info('Connecting')
        async with websockets.connect(self._config.get('HomeAssistant', 'websocket')) as websocket:
            LOGGER.debug('Websocket connected')
            client = Client(self._config.get('MQTT', 'host'))
            client._client.username_pw_set(self._config.get('MQTT', 'username'), self._config.get('MQTT', 'password'))
            async with client as mqtt_session:
                LOGGER.debug('MQTT connected')
                self._ws_handler = WebsocketHandler(self._config, websocket, mqtt_session)
                await self._ws_handler.run()
        LOGGER.info('Shut down')

    async def shutdown(self):
        LOGGER.info('Shutting down')
        await self._ws_handler.shutdown()


class WebsocketHandler():

    def __init__(self, config: ConfigParser, websocket, mqtt_session):
        self._config = config
        self._ids = id_seq()
        self._messages = {}
        self._websocket = websocket
        self._mqtt_session = mqtt_session
        self._rooms = []
        self._state_listeners = {}
        self._running = True
        self._initial_state = {}
        if os.path.exists('state.json'):
            with open('state.json') as in_f:
                self._initial_state = json.load(in_f)

    async def run(self):
        while self._running:
            try:
                msg = json.loads(await wait_for(self._websocket.recv(), 5))
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
                #    'event_type': 'area_registry_updated'
                #}))
                #await websocket.send(json.dumps({
                #    'id': next(ids),
                #    'type': 'subscribe_events',
                #    'event_type': 'device_registry_updated'
                #}))
                elif msg['type'] == 'auth_invalid':
                    LOGGER.debug('Authentication failed')
                    self._running = False
                else:
                    if msg['id'] in self._messages:
                        msg_type = self._messages[msg['id']]
                        if msg_type == 'config/area_registry/list':
                            self._rooms = [RoomController(self,
                                                          self._mqtt_session,
                                                          room,
                                                          self._initial_state['rooms'][room['area_id']]
                                                          if 'rooms' in self._initial_state and room['area_id'] in self._initial_state['rooms']
                                                          else {})
                                           for room in msg['result']]
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
                            await self._update_states(msg['result'])
                            del self._messages[msg['id']]
                            await self.send_message('subscribe_events',
                                                    {'event_type': 'state_changed'})
                        elif msg_type == 'subscribe_events' and msg['type'] == 'event':
                            if msg['event']['event_type'] == 'state_changed':
                                await self._update_states([msg['event']['data']['new_state']])
                        elif msg_type == 'call_service':
                            del self._messages[msg['id']]
            except TimeoutError:
                pass

    async def shutdown(self):
        LOGGER.debug('Disconnecting')
        state = {'rooms': {}}
        for room in self._rooms:
            state['rooms'][room.room_id] = await room.shutdown()
        with open('state.json', 'w') as out_f:
            json.dump(state, out_f)
        self._running = False

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

    def add_state_listener(self, entity_id, listener):
        if entity_id in self._state_listeners:
            if listener not in self._state_listeners:
                self._state_listeners[entity_id].append(listener)
        else:
            self._state_listeners[entity_id] = [listener]

    async def _update_states(self, states):
        for state in states:
            if state['entity_id'] in self._state_listeners:
                for listener in self._state_listeners[state['entity_id']]:
                    await listener.state_update(state['entity_id'], state)
