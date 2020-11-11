import asyncio
import json
import logging


LOGGER = logging.getLogger('smartish_home.climate')


class ClimateComponent():

    def __init__(self, websocket, mqtt_session, room_id, room_name, initial_state):
        self._component_id = f'{room_id}-sh-cc'
        self._room_name = room_name
        LOGGER.debug(f'Creating Climate Control {self._room_name}')
        self._temperature = {}
        self._climate = {}
        self._websocket = websocket
        self._mqtt_session = mqtt_session
        self._current_temperature = 'unknown'
        self._target_temperature = initial_state['target_temperature'] if 'target_temperature' in initial_state else 10
        self._mode = initial_state['mode'] if 'mode' in initial_state and initial_state['mode'] in ['heat', 'off'] else 'off'
        self._tasks = []
        self._connected = False

    async def add_climate(self, climate):
        self._climate[climate['entity_id']] = climate
        self._websocket.add_state_listener(climate['entity_id'], self)
        if self._climate and self._temperature and not self._connected:
            await self._connect()

    async def add_temperature(self, temperature):
        self._temperature[temperature['entity_id']] = temperature
        self._websocket.add_state_listener(temperature['entity_id'], self)
        if self._climate and self._temperature and not self._connected:
            await self._connect()

    async def state_update(self, entity_id, state):
        if entity_id in self._climate:
            self._climate[entity_id]['state'] = state
            await self._update()
        elif entity_id in self._temperature:
            self._temperature[entity_id]['state'] = state
            await self._update()

    async def shutdown(self):
        LOGGER.debug(f'Shutting down Climate Control {self._room_name}')
        await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/config', '')
        for task in self._tasks:
            task.cancel()
        self._connected = False
        LOGGER.debug(f'Shut down Climate Control {self._room_name}')
        return {'mode': self._mode,
                'target_temperature': self._target_temperature}

    async def _listen_target_temperature(self):
        async with self._mqtt_session.filtered_messages(f'homeassistant/climate/{self._component_id}/targetTempCmd') as messages:
            await self._mqtt_session.subscribe(f'homeassistant/climate/{self._component_id}/targetTempCmd')
            async for message in messages:
                self._target_temperature = float(message.payload.decode())
                await self._update()
                await self._websocket.send_message()

    async def _listen_mode(self):
        async with self._mqtt_session.filtered_messages(f'homeassistant/climate/{self._component_id}/thermostatModeCmd') as messages:
            await self._mqtt_session.subscribe(f'homeassistant/climate/{self._component_id}/thermostatModeCmd')
            async for message in messages:
                if message.payload.decode() == 'heat':
                    self._mode = 'heat'
                elif message.payload.decode() == 'off':
                    self._mode = 'off'
                await self._update()

    async def _connect(self):
        LOGGER.debug(f'Creating MQTT Climate Control {self._room_name}')
        self._connected = True
        message = {
            'name': self._room_name,
            'mode_command_topic': f'homeassistant/climate/{self._component_id}/thermostatModeCmd',
            'mode_state_topic': f'homeassistant/climate/{self._component_id}/mode',
            'action_topic': f'homeassistant/climate/{self._component_id}/action',
            'availability_topic': f'homeassistant/climate/{self._component_id}/available',
            'payload_available': 'online',
            'payload_not_available': 'offline',
            'temperature_command_topic': f'homeassistant/climate/{self._component_id}/targetTempCmd',
            'temperature_state_topic': f'homeassistant/climate/{self._component_id}/targetTemp',
            'current_temperature_topic': f'homeassistant/climate/{self._component_id}/currentTemp',
            'min_temp': '10',
            'max_temp': '28',
            'temp_step': '0.1',
            'modes': ['off', 'heat'],
            'unique_id': f'{self._component_id}-th',
            'device': {
                'manufacturer': 'Smartish Home',
                'model': 'Room Climate Control',
                'identifiers': [self._component_id],
                'name': 'Room Climate Control'
            },
        }
        self._tasks = [
            asyncio.get_event_loop().create_task(self._listen_target_temperature()),
            asyncio.get_event_loop().create_task(self._listen_mode())
        ]
        await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/config', json.dumps(message))
        asyncio.create_task(self._delayed_update())

    async def _delayed_update(self, delay=5):
        await asyncio.sleep(delay)
        await self._update()

    async def _update(self):
        LOGGER.debug(f'Updating Climate Control {self._room_name}')
        temperatures = [float(t['state']['state'])
                        for t in self._temperature.values() if t['state']['state'] != 'unknown']
        climates = [float(c['state']['attributes']['temperature'])
                    for c in self._climate.values() if c['state']['attributes']['temperature'] != 'unknown']
        awaitables = []
        if temperatures and climates:
            cur_temperature = sum(temperatures) / len(temperatures)
            awaitables.append(self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/available', 'online'))
            awaitables.append(self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/currentTemp', '{0:.1f}'.format(cur_temperature)))
            awaitables.append(self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/targetTemp', '{0:.1f}'.format(self._target_temperature)))
            awaitables.append(self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/mode', self._mode))
            if self._mode == 'heat' and abs(max(climates) - 28) < 0.01:
                awaitables.append(self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/action', 'heating'))
            else:
                awaitables.append(self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/action', 'off'))
            if self._mode == 'heat':
                if cur_temperature < self._target_temperature:
                    for key, value in self._climate.items():
                        if '_commanded' not in value or value['_commanded'] != 28:
                            value['_commanded'] = 28
                            awaitables.append(self._websocket.send_message('call_service', payload={
                                'domain': 'climate',
                                'service': 'set_temperature',
                                'service_data': {
                                    'entity_id': key,
                                    'temperature': 28
                                }
                            }))
                else:
                    for key, value in self._climate.items():
                        if '_commanded' not in value or value['_commanded'] != 10:
                            value['_commanded'] = 10
                            awaitables.append(self._websocket.send_message('call_service', payload={
                                'domain': 'climate',
                                'service': 'set_temperature',
                                'service_data': {
                                    'entity_id': key,
                                    'temperature': 10
                                }
                            }))
            else:
                for key, value in self._climate.items():
                    if '_commanded' not in value or value['_commanded'] != 10:
                        value['_commanded'] = 10
                        awaitables.append(self._websocket.send_message('call_service', payload={
                            'domain': 'climate',
                            'service': 'set_temperature',
                            'service_data': {
                                'entity_id': key,
                                'temperature': 10
                            }
                        }))
        else:
            awaitables.append(self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/available', 'offline'))
            awaitables.append(self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/currentTemp', 'unknown'))
        await asyncio.gather(*awaitables)
