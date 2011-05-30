from __future__ import absolute_import

import os
import re

from imdb import IMDb
from simpleapi import Namespace, serialize

from kinoknecht import config
from kinoknecht.database import db_session
from kinoknecht.models import Videofile, Movie, Show, Episode
from kinoknecht.player import Player

CATEGORIES = {'file': Videofile, 'movie': Movie, 'show': Show,
              'episode': Episode, 'unassigned': Videofile}

imdb = IMDb()
player = Player(config.extra_args)

class DBApi(Namespace):
    def create(category, vfiles=None, imdbid=None, title=None):
        if not imdbid and not title:
            return "Please specifiy either a title or an imdb id!"
        if category not in CATEGORIES:
            return "Invalid category!"
        vfiles = [Videofile.get(int(x)) for x in vfiles]
        if 'imdbid':
            imdbid = int(imdbid)

        obj = None
        if category == 'movie':
            obj = Movie(videofiles=vfiles)
        elif category == 'show':
            obj = Show()
        elif category == 'episode':
            obj = Episode(vfiles[0])

        try: obj.title = title
        except NameError: pass
        try: obj.imdb_id = int(imdbid)
        except NameError: pass

        db_session.add(obj)
        db_session.commit()
        return obj.id
    create.published = True

    def query(category, searchstr):
        """Simple query for objects by name"""
        try: objtype = CATEGORIES[category]
        except KeyError: return "Invalid category!"
        results = [dict(id=entry.id, title=entry.title) for entry in
                objtype.query.filter(objtype.title.like('%' + searchstr + '%'))]
        return serialize(results)
    query.published = True

    def add_to_show(showid, episodes):
        """Adds one or more episodes to a show"""
        showid = int(showid)
        episodes = [Episode.get(int(x)) for x in episodes]
        show = Show.get(showid)
        for epi in episodes:
            show.episodes.append(epi)
        return True
    add_to_show.published = True

    def query_imdb(searchstr):
        results = [dict(imdbid=entry.movieID,
            title=entry['long imdb canonical title'])
            for entry in imdb.search_movie(searchstr)]
        return serialize(results[0:9])
    query_imdb.published = True

    def get_clean_name(fname=None, vfid=None):
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
        Videofile.update_all()
        return True
    update_database.published = True

class PlayerApi(Namespace):
    def play(category, id):
        vfile = Videofile.get(id)
        player.loadfile(os.path.join(vfile.path, vfile.name))
        return True
    play.published = True

    def pause():
        player.pause()
        return True
    pause.published = True

    def stop():
        player.stop()
        return True
    stop.published = True

    def seek(position):
        player.seek(position)
        return True
    seek.published = True

    def load_subtitle(subid):
        subpath = os.path.abspath(Videofile.subfilepaths[subid])
        player.sub_load(subpath)

    def get_position():
        return player.time_pos

