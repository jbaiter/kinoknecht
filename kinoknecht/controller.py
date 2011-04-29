from __future__ import unicode_literals
from __future__ import absolute_import

import os
import logging
import re
from mimetypes import types_map

import imdb
from sqlalchemy import create_engine
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import and_

from kinoknecht.model import (Session, Base, Videofile, Movie, Episode, Show,
                              Person, Company)


def get_video_mimetypes():
    # TODO: Why rely on mimetypes at all? Get list of supported video codecs
    #       from mplayer and generate a list of extensions from that
    types = [k for (k, v) in types_map.iteritems() if 'video' in v]
    types = tuple(types + [i for i in\
      ['.wmv', '.flv', '.mkv', '.rm', '.m2v'] if i not in types])
    return types


def to_unicode(string):
    #TODO: This smells, there must be a more proper way to do this
    if not isinstance(string, unicode):
        return unicode(string, errors='replace')
    else:
        return string


class Controller(object):
    """
    Populates, updates and provides access to the database by walking the
    filetree, taking care of obtaining the data corresponding to each file and
    collection specified by the user
    """

    # Supported file extensions for videos and subtitles
    # Video filetypes are taken from the MIME types installed on the system
    # and extended with other filetypes mplayer can usually handle.
    _ftypes_vid = get_video_mimetypes()
    _movie_regex_list = [re.compile(
        r'(?P<basename>.*)(?P<num>\d+) *of *(?:\d+).*', re.I),
                        re.compile(
        r'(?P<basename>.*)(?:CD|DVD|Disc|Part) *(?P<num>\d+).*', re.I)]
    _episode_regex_list = [re.compile(
        r'(?P<basename>.*)(?:S(?P<season>\d+)E(?P<episode>\d+)).*', re.I),
                           re.compile(
        r'(?P<basename>.*)(?P<season>\d)(?P<episode>\d{2,3}).*', re.I)]

    def __init__(self, dbfile, *videodirs):
        """
        Set up database connection and filesystem monitor
        """
        self._logger = logging.getLogger("controller")
        self._setup_db(dbfile)
        #self._setup_fswatcher()
        self._setup_imdb()
        # Scan video directories at initialization if specified
        if videodirs:
            self._videodirs = videodirs
            for viddir in videodirs:
                #TODO: Move this to 'add_videodir' and 'update_videodir'
                self._scan_videodir(viddir)
                #self._add_watchdir(viddir)

    #___________________________Public API_____________________________________
    def browse(self, path=None):
        """
        Returns a listing of all videofiles and subdirectories in a given
        (absolute!) path
        """

        # Return list of root-level video directories (as specified in config)
        if not path:
            return [[{'path':x} for x in self._videodirs], []]

        qresult = self._session.query(Videofile).filter(
            Videofile.path.like('%' + path + '%'))

        # Get subdirs
        subdirs = []
        for i in qresult:
            splitpath = os.path.split(i.path)
            if splitpath[0] == path and {'path': i.path} not in subdirs:
                ndict = {'path': i.path}
                subdirs.append(ndict)

        # Get videofiles
        vfiles = [{'id':i.id, 'name':i.name} for i in\
            self._session.query(Videofile).filter_by(path=path)]

        return [subdirs, vfiles]

    def statistics(self):
        """
        Returns statistics of the database.
        """
        stat_dict = {}
        vidfile_iter = self._session.query(Videofile)
        stat_dict['vidfile_count'] = self._session.query(Videofile).count()
        stat_dict['movie_count'] = self._session.query(Movie).count()
        stat_dict['show_count'] = self._session.query(Show).count()
        stat_dict['episode_count'] = self._session.query(Episode).count()
        stat_dict['total_size'] = sum([x.size for x in vidfile_iter])
        stat_dict['total_length'] = sum([x.length for x in vidfile_iter
                                        if x.length])
        return stat_dict

    def list_videos(self):
        """
        Returns a list of all Videofile objects in the database.
        """
        vidlist = [{'id': x.id, 'path': x.path, 'name': x.name}\
            for x in self._session.query(Videofile)]
        return vidlist

    def details(self, typestr, objid):
        """
        For the file of type <typestr> with the id <id> return a dictionary
        with all available public information.
        """
        valid_types = {'file': Videofile, 'movie': Movie, 'show': Show,
            'episode': Episode, 'person': Person, 'company': Company}
        if typestr not in valid_types.keys():
            #TODO: Return an error message
            return {}
        queryobj = valid_types[typestr]
        try:
            result = self._session.query(queryobj).filter_by(
                id=objid).one().get_infodict()
            # JSON does not have a datetime type, so we pass a ISO formatted
            # string
            if 'creation_date' in result.keys():
                result['creation_date'] = result['creation_date'].isoformat()
        except NoResultFound:
        #FIXME: There should be some kind of message to the user here!
            result = {}
        return result

    def search_videofile(self, *sterms):
        """
        Accepts an arbitrary number of dictionaries with three keys 'field',
        'operator' and 'value'. The single queries are then chained via 'AND'.

        'operator' can be one of ['like',
                                  'equals', 'not equals',
                                  'greater', 'lesser']
        Example:  search([
                    {'field':'name', 'operator':'like', 'value':'seinfeld'},
                    {'field':'length', 'operator':'lesser', 'value':3000}
                  ])
        """
        db_fields = [f for f in dir(Videofile) if not\
                        f.startswith('_')]

        conditions = []
        for sdict in sterms:
            if not len(sdict) == 3:
                raise Exception(
                    "Insufficient arguments! Needs 'field', 'operator' and"
                    "'value.'")
            if not sdict['field'] in db_fields:
                raise ValueError(
                    "Invalid field! Needs one of %s" % str(db_fields)
                    )
            if sdict['operator'] == 'equals':
                conditions.append(
                    Videofile.__dict__[sdict['field']] == sdict['value'])
            elif sdict['operator'] == 'not equals':
                conditions.append(
                    Videofile.__dict__[sdict['field']] != sdict['value'])
            elif sdict['operator'] == 'like':
                conditions.append(
                    Videofile.__dict__[sdict['field']].like(
                        "%" + sdict['value'] + "%")
                    )
            elif sdict['operator'] == 'greater':
                conditions.append(
                    Videofile.__dict__[sdict['field']] > sdict['value'])
            elif sdict['operator'] == 'lesser':
                conditions.append(
                    Videofile.__dict__[sdict['field']] < sdict['value'])
            else:
                raise ValueError(
                    """Invalid operator %s!""" % sdict['operator']
                    )

        results = [x.__dict__ for x in\
            self._session.query(Videofile).filter(and_(*conditions))]
        return results

    def search_metadata(self, searchterm):
        """
        Searches IMDB for the specified searchterm and returns a list of
        dictionaries with title and movieID.
        """
        s_result = self._imdb.search_movie(searchterm)
        results = [{'title': x['long imdb canonical title'],
                    'id': int(x.movieID)} for x in s_result]
        return results

    def create_movie(self, vfids, title=None, imdbid=None):
        """
        Creates a Movie with the selected Videofiles and fetches its metadata
        from imdb if an imdbid is specified.
        """
        
        movie = Movie(title=title, imdb_id=imdbid)
        for vfid in vfids:
            vf = self._session.query(Videofile).get(vfid)
            movie.videofiles.append(vf)
        if imdbid:
            movie.update_metadata()
        self._session.add(movie)
        self._session.commit()
        return movie

    def create_show(self, basename=None, imdbid=None):
        show = Show(basename=basename, imdb_id=imdbid)
        if imdbid:
            show.update_metadata()
        self._session.add(show)
        self._session.commit()
        return show
    
    def create_episode(self, season_num, episode_num, show=None):
        episode = Episode(season_num=season_num, episode_num=episode_num,
                          show=show)
        if show.imdb_id:
            show_episodes = self._imdb.get_movie_episodes(show.imdb_id)
            episode.imdb_id = show_episodes['data']['episodes'][int(
                season_num)][int(episode_num)].movieID
            episode.update_metadata()
        self._session.add(episode)
        return episode


    #__________________________Private API_____________________________________
    def _setup_db(self, dbfile):
        #TODO: Move this to the module initializer?
        engine = create_engine('sqlite:///' + dbfile)
        Base.metadata.bind = engine
        Base.metadata.create_all()
#        Session.configure(bind=engine)
        self._session = Session()
        self._logger.debug("Connected to Database")

    def _setup_imdb(self):
        self._imdb = imdb.IMDb()

    def _scan_videodir(self, path):
        """
        Search recursively for supported video files.
        """
        #TODO:  Only collect files to be added and add them all at once to the
        #       db to improve performance
        self._logger.info(u"Scanning directory '%s' for video files" % path)
        scanobjs = []
        vidtree = self._search_ftree(path, self._ftypes_vid)
        for viddir in vidtree.keys():
            for vidfile in vidtree[viddir]:
                # Does the file already exist in the db?
                dbentries = self._session.query(Videofile).filter_by(
                    name=to_unicode(vidfile))
                if not dbentries.count():
                    vfobj = Videofile(viddir, vidfile)
                    vfobj.find_subtitle()
                    scanobjs.append(vfobj)
                else:
                    # Seems like it, see if there's something to update
                    for vfobj in dbentries:
                        self._check_videofile(vfobj, viddir)
        self._session.add_all(scanobjs)
        self._session.commit()
        self._find_multifile_movies(*scanobjs)
        self._find_episodes(*scanobjs)

    def _check_videofile(self, vfobject, path):
        """
        Checks if file still exists in its path and updates the entry if it has
        been moved.
        """
        if path == vfobject.path:
            # Nothing to update here!
            return
        if not os.path.exists(os.path.join(vfobject.path, vfobject.name)):
            vfobject.path = path
            vfobject.save()
            self._logger.info(u"Updated video file %s" % vfobject.name)
        else:
            # Seems we have a duplicate!
            self._logger.warning(u"File with name '%s' already exists in"
                "the database, might be a duplicate!" % vfobject.name)
            new_vfobj = Videofile(path, vfobject.name)
            self._session.add(new_vfobj)

    def _find_multifile_movies(self, *videofiles):
        """
        Finds movies that are split across several CDs/DVDs among the
        specified Videofile objects and creates Movie objects for them.
        """

        # Find all related files among videofiles
        relfiledict = {}
        for vf in videofiles:
            for r in self._movie_regex_list:
                m = r.match(vf.name)
                if m:
                    break
            try:
                basename = m.group('basename')
            # This means the files are named like 'cd1.avi', etc, so we
            # try to derive the basename from the parent directory
            except:
                basename = os.path.basename(vf.path)
            if not basename in relfiledict.keys():
                relfiledict[basename] = [vf.id]
            else:
                relfiledict[basename].append(vf.id)

        # Create Movies for the files
        for (basename, files) in relfiledict.iteritems():
            #TODO: Query IMDb with basename as query to find metadata?
            self.create_movie(files, title=basename)

    def _find_episodes(self, *videofiles):
        """
        Finds episodes and creates Episode and Show objects for them.
        """
        for vf in videofiles:
            for r in self._episode_regex_list:
                m = r.match(vf.name)
                if m:
                    break
            if not m:
                return
            basename = m.group('basename')
            season_num = m.group('season')
            episode_num = m.group('episode')
            query = self._session.query(Show).filter_by(basename=basename)
            if query.count() != 1:
                show = self.create_show(basename)
                self._session.add(show)
            else:
                show = query.one()
            episode = self.create_episode(season_num, episode_num)
            episode.show = show
#            show.episodes.append(episode)
            self._session.add(episode)
        self._session.commit()

    def _search_ftree(self, path, ftypes):
        """
        Walk the filetree to find files with specified extensions
        """

        filedict = {}
        for root, dirs, files in os.walk(to_unicode(path)):
            matchlist = []
            for name in files:
                if name.endswith(ftypes):
                    matchlist.append(name)
            if len(matchlist) > 0:
                filedict[root] = matchlist
        return filedict