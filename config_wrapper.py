import configparser
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


config = None
config = configparser.ConfigParser()


def initialize(version):
    if version == 0:
        logger.info('Loading first config')
        config.read('config.ini')
    elif version == 1:
        print('Loading second config')
        config.read('config2.ini')
    else:
        print('Loading third config')
        config.read('config3.ini')