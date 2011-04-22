from __future__ import absolute_import

import logging

from wsgiref.simple_server import make_server
import lovely_jsonrpc.dispatcher
import lovely_jsonrpc.wsgi

from kinoknecht.controller import Controller
from kinoknecht.player import Player


class Kinoknecht(object):
    def __init__(self, address, port, dbfile, video_dirs, player_args):
        self.logger = logging.getLogger("kinoknecht")

        # Start backend
        self.controller = Controller(dbfile, *video_dirs)
        self.player = Player(args=player_args)

        # Set up the WSGI/JSONRPC server
        player_dispatcher = lovely_jsonrpc.dispatcher.JSONRPCDispatcher(
            self.player)
        ctrl_dispatcher = lovely_jsonrpc.dispatcher.JSONRPCDispatcher(
            self.controller)
        app = lovely_jsonrpc.wsgi.WSGIJSONRPCApplication(
            {'player': player_dispatcher,
             'collection': ctrl_dispatcher}
            )
        self.server = make_server(address, port, app)

    def serve(self):
        # Start the server
        self.logger.info("Serving Kinoknecht on %s:%d"\
            % self.server.server_address)
        while True:
            try:
                self.server.handle_request()
            except KeyboardInterrupt:
                self.player.quit()
