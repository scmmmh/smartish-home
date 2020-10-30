import logging


LOGGER = logging.getLogger('smartish_home.climate')


class ClimateComponent():

    def __init__(self, temperature, climate):
        self._temperature = temperature
        self._climate = climate

    def update_entities(self, temperature, climate):
        self._temperature = temperature
        self._climate = climate
