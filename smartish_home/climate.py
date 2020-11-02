import logging


LOGGER = logging.getLogger('smartish_home.climate')


class ClimateComponent():

    def __init__(self, room_id):
        self._component_id = f'{room_id}:cc'
        self._temperature = []
        self._climate = []
        LOGGER.debug(f'Creating Climate Control {self._component_id}')

    async def connect(self):
        pass

    async def update_entities(self, temperature, climate):
        self._temperature = temperature
        self._climate = climate
