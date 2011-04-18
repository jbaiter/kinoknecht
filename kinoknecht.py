#!/usr/bin/env python
from __future__ import absolute_import

import logging
import os
import sys
import ConfigParser

from kinoknecht import Kinoknecht

LOGLEVELS = {'debug':logging.DEBUG, 'info':logging.INFO,
             'warning':logging.WARNING, 'error':logging.ERROR,
             'critical':logging.CRITICAL}

if __name__ == '__main__':
    # Read configuration
    config = ConfigParser.ConfigParser()
    config.readfp(open('default.cfg'))
    config.read(['/etc/kinoknecht.cfg', os.path.expanduser(
      '~/.kinoknecht/kinoknecht.cfg')])

    # Start logging
    log_file = os.path.expanduser(config.get('Main', 'log_file'))
    log_level = LOGLEVELS.get(config.get('Main', 'log_level'),
        logging.NOTSET)
    if not os.path.exists(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))
    filelog_format = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(filename=log_file, level=log_level,
        format=filelog_format)
    
    # Set up console output for easier debugging
    # TODO: Trigger this via cmdline option
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    ch.setFormatter(formatter)
    logging.getLogger('').addHandler(ch)

    host = config.get('Server', 'address')
    port = int(config.get('Server', 'port'))
    dbfile = os.path.expanduser(config.get('Main', 'db_file'))
    if not os.path.exists(os.path.dirname(dbfile)):
        os.makedirs(os.path.dirname(dbfile))
    video_dirs = config.get('Main', 'video_dirs').strip('"').split('", "')
    player_args = config.get('Player', 'extra_args')

    k = Kinoknecht(host, port, dbfile, video_dirs, player_args)
    k.serve()
    # TODO: Make the program quit gracefully (interference with player!)
    sys.exit()
    
