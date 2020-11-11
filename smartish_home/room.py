import logging

from .climate import ClimateComponent


LOGGER = logging.getLogger('smartish_home.room')


class RoomController():
    """Smartish Control of a single HomeAssistant Area."""

    def __init__(self, websocket, mqtt_session, settings: dict, initial_state: dict):
        self.room_id = f'{settings["area_id"]}'
        self._name = settings['name']
        self._devices = {}
        self._entities = {}
        self._climate_component = ClimateComponent(websocket,
                                                   mqtt_session,
                                                   self.room_id,
                                                   self._name,
                                                   initial_state['climate'] if 'climate' in initial_state else {})
        self._websocket = websocket
        self._mqtt_session = mqtt_session
        LOGGER.debug(f'Created {self._name}')
        print(initial_state)

    async def add_devices(self, devices: list):
        for device in devices:
            if device['area_id'] == self.room_id:
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
                    self._websocket.add_state_listener(entity['entity_id'], self)

    async def state_update(self, entity_id, state):
        entity = self._entities[entity_id]
        entity['state'] = state
        if 'device_class' not in entity:
            if 'state' in entity:
                if 'device_class' in entity['state']['attributes']:
                    entity['device_class'] = entity['state']['attributes']['device_class']
                else:
                    entity['device_class'] = entity['entity_id'].split('.')[0]
                    if entity['device_class'] == 'sensor':
                        if 'unit_of_measurement' in entity['state']['attributes']:
                            if entity['state']['attributes']['unit_of_measurement'] == '°C':
                                entity['device_class'] = 'temperature'
                if entity['device_class'] == 'climate':
                    await self._climate_component.add_climate(entity)
                elif entity['device_class'] == 'temperature':
                    await self._climate_component.add_temperature(entity)

    async def shutdown(self):
        LOGGER.debug(f'Shutting down {self._name}')
        state = {}
        if self._climate_component:
            state['climate'] = await self._climate_component.shutdown()
            self._climate_component = None
        return state
