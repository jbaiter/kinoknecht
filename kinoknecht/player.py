import logging

import mplayer

#TODO: Do we really need to subclass mplayer.Player? What for?
#TODO: Abstract to allow for multiple player backends (VLC? Gstreamer? Xine?)


class Player(mplayer.Player):
    """
    Handles playback of Videofiles.
    """

    def __init__(self, args):
        self.logger = logging.getLogger("kinoknecht.player.Player")
        self.logger.debug("Creating instance of Player")
        super(Player, self).__init__(args, stderr=mplayer.STDOUT)
