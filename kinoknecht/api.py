from __future__ import absolute_import

import json
import os
import re

from imdb import IMDb
from simpleapi import Namespace 

from kinoknecht import config
from kinoknecht.database import db_session
from kinoknecht.models import Videofile, Movie, Show, Episode
from kinoknecht.player import Player

CATEGORIES = {'file': Videofile, 'movie': Movie, 'show': Show,
              'episode': Episode, 'unassigned': Videofile}

imdb = IMDb()
player = Player(config.extra_args)

class DBApi(Namespace):
    def create(self, category, vfiles=None, imdbid=None, title=None):
        """ Creates a new object in the given category, optionally assigning
            vfiles, imdbid and/or title to it.
        """
        if not imdbid and not title:
            return "Please specifiy either a title or an imdb id!"
        if category not in CATEGORIES:
            return "Invalid category!"
        if vfiles:
            vfiles = [Videofile.get(int(x)) for x in vfiles]
        if imdbid:
            imdbid = int(imdbid)

        obj = None
        if category == 'movie':
            obj = Movie(videofiles=vfiles)
        elif category == 'show':
            obj = Show()
        elif category == 'episode':
            obj = Episode(vfiles[0])

        if obj.title:
            obj.title = title
        if obj.imdb_id:
            obj.imdb_id = int(imdbid)

        db_session.add(obj)
        db_session.commit()
        return obj.id
    create.published = True

    def query(self, category, searchstr):
        """Simple query for objects by category and name"""
        try: objtype = CATEGORIES[category]
        except KeyError: return "Invalid category!"
        results = [dict(id=entry.id, title=entry.title) for entry in
                objtype.query.filter(objtype.title.like('%' + searchstr + '%'))]
        return json.dumps(results)
    query.published = True

    def add_to_show(self, showid, episodes):
        """Adds one or more episodes to a show"""
        showid = int(showid)
        episodes = [Episode.get(int(x)) for x in episodes]
        show = Show.get(showid)
        for epi in episodes:
            show.episodes.append(epi)
        return True
    add_to_show.published = True

    def query_imdb(self, searchstr):
        """Queries IMDb and returns a list of results"""
        results = [dict(imdbid=entry.movieID,
            title=entry['long imdb canonical title'])
            for entry in imdb.search_movie(searchstr)]
        return json.dumps(results[0:9])
    query_imdb.published = True

    def get_clean_name(self, fname=None, vfid=None):
        #FIXME: There seems to be a nasty bug in simpleapi relating to
        #       years in filenames. Try running the tests and see foryourself.
        """ Returns a cleaned up version of fname (or of fname of Videofile
            with vfid) to facilitate imdb queriyng.
        """
        #TODO: Move this to a Videofile method?
        if not fname and not vfid:
            raise Exception(
                    'Insufficient arguments, specify either fname or vfid')
        # For files that comply to scene filenaming "standards"
        scene_rexp = re.compile(r'([\w\s]+)( \d{4})? (.+Rip) .*', re.I)
        # That is one nasty sunnufabitch...
        rexp = re.compile(r'(?:\d{4}\s*\-\s*?)?(?:[\w\s]*-\s*)?([\w\s\.\-]+)(?:\(?\d{4}\)?)?.*', re.I)
        if not fname:
            fname = Videofile.get(int(vfid)).name
        # Normalize the name by removing the extension and all dots
        fname = os.path.splitext(fname)[0].replace('.', ' ')
        # Do we have a scene filename?
        fname_match = scene_rexp.match(fname)
        if fname_match:
            return fname_match.groups()[0].strip()
        # Doesn't look like it, let's be more fuzzy
        fname_match = rexp.match(fname)
        if fname_match:
            return fname_match.groups()[0].strip()
        # We give up and just return the normalized name
        else:
            return fname
    get_clean_name.published = True

    def update_database(self):
        """Tells the database to update all its directories"""
        Videofile.update_all()
        return True
    update_database.published = True

class PlayerApi(Namespace):
    def play(self, category, id):
        vfile = Videofile.get(id)
        player.loadfile(os.path.join(vfile.path, vfile.name))
        return True
    play.published = True

    def pause(self):
        player.pause()
        return True
    pause.published = True

    def stop(self):
        player.stop()
        return True
    stop.published = True

    def seek(self, position):
        player.seek(position)
        return True
    seek.published = True

    def load_subtitle(self, subid):
        subpath = os.path.abspath(Videofile.subfilepaths[subid])
        player.sub_load(subpath)

    def get_position(self):
        return player.time_pos

