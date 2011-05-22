#!/usr/bin/env python
from __future__ import absolute_import
import logging

from kinoknecht.database import init_db
from kinoknecht.models import Videofile


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    init_db()
    Videofile.update_all()
