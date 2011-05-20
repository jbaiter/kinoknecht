from __future__ import absolute_import

from simpleapi import Namespace, serialize

from kinoknecht.helpers import CATEGORIES
from kinoknecht.database import db_session
from kinoknecht.models import Videofile, Movie, Show, Episode
from kinoknecht.player import Player



class DBApi(Namespace):
    def query_imdb(searchstr):
        results = [dict(imdbid=entry.movieID,
            title=entry['long imdb canonical title'])
            for entry in i.search_movie(searchstr)]
        return serialize(results[0:9])
    query_imdb.published = True

    def create(category, vfiles, imdbid=None, title=None):
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
            try: mov.imdb_id = int(imdbid)
            except NameError: pass
        elif category == 'show':
            obj = Show()
            try: show.title = title
            except NameError: pass
        elif category == 'episode':
            episode = Episode(vfiles[0])
        db_session.add(mov)
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
