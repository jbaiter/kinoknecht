from __future__ import absolute_import

import logging
import os

import config

LOGLEVELS = {'debug': logging.DEBUG, 'info': logging.INFO,
             'warning': logging.WARNING, 'error': logging.ERROR,
             'critical': logging.CRITICAL}


def setup_logging():
    # Start logging
    log_file = os.path.abspath(config.log_file)
    log_level = LOGLEVELS.get(config.log_level,
        logging.NOTSET)
    if not os.path.exists(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))
    filelog_format = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(filename=log_file, level=log_level,
        format=filelog_format)

    # Set up console output for easier debugging
    # TODO: Trigger this via cmdline option
    kk_logger = logging.getLogger('kinoknecht')
    kk_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    kk_handler.setFormatter(formatter)
    kk_logger.addHandler(kk_handler)

setup_logging()
