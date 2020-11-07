import logging

from .climate import ClimateComponent


LOGGER = logging.getLogger('smartish_home.room')


class RoomController():
    """Smartish Control of a single HomeAssistant Area."""

    def __init__(self, websocket, mqtt_session, settings: dict):
        self._room_id = settings['area_id']
        self._name = settings['name']
        self._devices = {}
        self._entities = {}
        self._climate_component = None
        self._websocket = websocket
        self._mqtt_session = mqtt_session
        LOGGER.debug(f'Created {self._name}')

    async def add_devices(self, devices: list):
        for device in devices:
            if device['area_id'] == self._room_id:
                if device['id'] in self._devices:
                    LOGGER.debug(f'Updating {device["name"]} in {self._name}')
                    self._devices[device['id']].update(device)
                else:
                    LOGGER.debug(f'Adding {device["name"]} to {self._name}')
                    self._devices[device['id']] = device

    async def add_entities(self, entities: list):
        for entity in entities:
            if entity['device_id'] in self._devices:
                if entity['disabled_by'] is None:
                    if entity['entity_id'] in self._entities:
                        LOGGER.debug(f'Updating {entity["name"]} in {self._name}')
                        self._entities[entity['entity_id']].update(entity)
                    else:
                        LOGGER.debug(f'Adding {entity["name"]} to {self._name}')
                        self._entities[entity['entity_id']] = entity

    async def update_states(self, states: list):
        changes = False
        for state in states:
            if state['entity_id'] in self._entities:
                LOGGER.debug(f'Updating {self._entities[state["entity_id"]]["name"]} in {self._name}')
                changes = True
                self._entities[state['entity_id']]['state'] = state
        if changes:
            await self._process_entities()
            if self._climate_component:
                await self._climate_component.update()

    async def _process_entities(self):
        changes = False
        for entity in self._entities.values():
            if 'device_class' not in entity:
                changes = True
                if 'state' in entity:
                    if 'device_class' in entity['state']['attributes']:
                        entity['device_class'] = entity['state']['attributes']['device_class']
                    else:
                        entity['device_class'] = entity['entity_id'].split('.')[0]
                        if entity['device_class'] == 'sensor':
                            if 'unit_of_measurement' in entity['state']['attributes']:
                                if entity['state']['attributes']['unit_of_measurement'] == '°C':
                                    entity['device_class'] = 'temperature'
        if changes:
            await self._setup_components()

    async def _setup_components(self):
        LOGGER.debug(f'Setting up {self._name}')
        climate = []
        temperature = []
        for entity in self._entities.values():
            if 'device_class' in entity:
                if entity['device_class'] == 'climate':
                    climate.append(entity)
                elif entity['device_class'] == 'temperature':
                    temperature.append(entity)
        if climate and temperature:
            if self._climate_component:
                LOGGER.debug(f'Updating the ClimateController for {self._name}')
                await self._climate_component.update_entities(temperature, climate)
            else:
                LOGGER.debug(f'Creating a ClimateController for {self._name}')
                self._climate_component = ClimateComponent(self._mqtt_session, self._room_id, self._name)
                await self._climate_component.connect()
                await self._climate_component.update_entities(temperature, climate)
