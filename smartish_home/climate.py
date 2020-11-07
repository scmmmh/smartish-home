import asyncio
import json
import logging


LOGGER = logging.getLogger('smartish_home.climate')


class ClimateComponent():

    def __init__(self, mqtt_session, room_id, room_name):
        self._component_id = f'{room_id}-sh-cc'
        LOGGER.debug(f'Creating Climate Control {self._component_id}')
        self._room_name = room_name
        self._temperature = {}
        self._climate = {}
        self._mqtt_session = mqtt_session
        self._current_temperature = 'unknown'
        self._target_temperature = 10
        self._mode = 'off'

    async def connect(self):
        LOGGER.debug(f'Creating MQTT Climate Control {self._component_id}')
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
        asyncio.get_event_loop().create_task(self._listen_target_temperature())
        asyncio.get_event_loop().create_task(self._listen_mode())
        await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/config', json.dumps(message))
        await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/available', 'offline')

    async def update_entities(self, temperature, climate):
        self._temperature.update(dict([(t['entity_id'], t) for t in temperature]))
        self._climate.update(dict([(c['entity_id'], c) for c in climate]))
        await self.update()

    async def _listen_target_temperature(self):
        async with self._mqtt_session.filtered_messages(f'homeassistant/climate/{self._component_id}/targetTempCmd') as messages:
            await self._mqtt_session.subscribe(f'homeassistant/climate/{self._component_id}/targetTempCmd')
            async for message in messages:
                self._target_temperature = float(message.payload.decode())
                await self.update()

    async def _listen_mode(self):
        async with self._mqtt_session.filtered_messages(f'homeassistant/climate/{self._component_id}/thermostatModeCmd') as messages:
            await self._mqtt_session.subscribe(f'homeassistant/climate/{self._component_id}/thermostatModeCmd')
            async for message in messages:
                if message.payload.decode() == 'heat':
                    self._mode = 'heat'
                elif message.payload.decode() == 'off':
                    self._mode = 'off'
                await self.update()

    async def update(self):
        LOGGER.debug(f'Updating ClimateController {self._component_id}')
        temperatures = [float(t['state']['state'])
                        for t in self._temperature.values() if t['state']['state'] != 'unknown']
        climates = [float(c['state']['attributes']['temperature'])
                    for c in self._climate.values() if c['state']['attributes']['temperature'] != 'unknown']
        if temperatures and climates:
            await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/available', 'online')
            await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/currentTemp', '{0:.1f}'.format(sum(temperatures) / len(temperatures)))
            await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/targetTemp', '{0:.1f}'.format(self._target_temperature))
            await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/mode', self._mode)
            if self._mode == 'heat' and abs(max(climates) - 28) < 0.01:
                await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/action', 'heating')
            else:
                await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/action', 'off')
        else:
            await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/available', 'offline')
            await self._mqtt_session.publish(f'homeassistant/climate/{self._component_id}/currentTemp', 'unknown')
