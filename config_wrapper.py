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
    else:
        print('Loading second config')
        config.read('config2.ini')
