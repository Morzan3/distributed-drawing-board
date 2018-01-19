import configparser
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


config = None
config = configparser.ConfigParser()
config.read('config.ini')
