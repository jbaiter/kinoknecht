from __future__ import unicode_literals

import pdb

import os
import logging
import re
from datetime import datetime
from mimetypes import types_map

import imdb
import pyinotify
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.pool import StaticPool, NullPool
from sqlalchemy.sql.expression import and_

from kinoknecht.midentify import midentify
from kinoknecht.model import Session, Base, Videofile, Movie, Episode, Show, Person, Company

def get_video_mimetypes():
    # TODO: Why rely on mimetypes at all? Get list of supported video codecs
    #       from mplayer and generate a list of extensions from that
    types = [k for (k, v) in types_map.iteritems() if 'video' in v]
    types = tuple(types + [i for i in\
      ['.wmv', '.flv', '.mkv', '.rm', '.m2v'] if i not in types])
    return types

def get_subtitle_mimetypes():
    types = ('.srt', '.ass', '.sub')
    return types

def to_unicode(string):
    #TODO: This smells, there must be a more proper way to do this
    if not isinstance(string, unicode):
        return unicode(string, errors='replace')
    else: return string

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
    _ftypes_sub = get_subtitle_mimetypes()
    _mask = pyinotify.IN_DELETE | pyinotify.IN_CLOSE_WRITE | \
        pyinotify.IN_MOVED_TO | pyinotify.IN_MOVED_FROM
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
        self._logger = logging.getLogger("kinoknecht.controller.Controller")
        self._setup_db(dbfile)
        #self._setup_fswatcher()
        self._setup_imdb()
        # Scan video directories at initialization if specified
        if videodirs:
            self._videodirs = videodirs
            for viddir in videodirs:
                #TODO: Move this to methods 'add_videodir' and 'update_videodir'
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

        qresult = self._session.query(Videofile).filter(Videofile.path.like('%' + path + '%'))

        # Get subdirs
        subdirs = []
        for i in qresult:
            splitpath = os.path.split(i.path)
            if splitpath[0] == path and {'path': i.path} not in subdirs:
                ndict = {'path': i.path}
                subdirs.append(ndict)
        
        # Get videofiles
        vfiles = [{'id' : i.id, 'name' : i.name} for i in\
            self._session.query(Videofile).filter_by(path=path)]

        return [subdirs, vfiles]


    def statistics(self):
        """
        Returns statistics of the database.
        """
        stat_dict = {}
        vidfile_iter = self._session.query(Videofile)
        stat_dict['vidfile_count'] = self._session.query(Videofile).count()
        stat_dict['total_size'] = sum([x.size for x in vidfile_iter])
        stat_dict['total_length'] = sum([x.length for x in vidfile_iter])
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
        valid_types = {'file':Videofile, 'movie':Movie, 'show':Show,
            'episode':Episode, 'person':Person, 'company':Company}
        if typestr not in valid_types.keys():
            #TODO: Return an error message
            return {}
        queryobj = valid_types[typestr]
        try:
            result = self._session.query(queryobj).filter_by(
                id=objid).one().__dict__ 
            # Filter out private attributes
            result = dict(
                (k,v) for (k,v) in result.iteritems() if not k.startswith('_'))
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
                    "Invalid field! Needs one of %s" % str(db_fields))
            if sdict['operator'] == 'equals':
                conditions.append(
                    Videofile.__dict__[sdict['field']] == sdict['value'])
            elif sdict['operator'] == 'not equals':
                conditions.append(
                    Videofile.__dict__[sdict['field']] != sdict['value'])
            elif sdict['operator'] == 'like':
                conditions.append(
                    Videofile.__dict__[sdict['field']].like("%"+sdict['value']+"%"))
            elif sdict['operator'] == 'greater':
                conditions.append(
                    Videofile.__dict__[sdict['field']] > sdict['value'])
            elif sdict['operator'] == 'lesser':
                conditions.append(
                    Videofile.__dict__[sdict['field']] < sdict['value'])
            else:
                raise ValueError("""Invalid operator %s!""" % sdict['operator'])

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


    def create_movie(self, vfids, imdbid):
        """
        Creates a Movie with the selected Videofiles and fetches its metadata
        from imdb.
        """
        moviemeta = self._imdb.get_movie(imdbid)
        self._imdb.update(moviemeta)
        
        movie = Movie()
        for vfid in vfids:
            vf = self._session.query(Videofile).get(vfid)
            movie.videofiles.append(vf)

        movie.title = moviemeta['smart canonical title']
        movie.alt_titles = str(moviemeta['akas'])
        movie.color_info = str(moviemeta['color info'])
        movie.cover_url = moviemeta['full-size cover url']
        movie.imdb_id = imdbid
        movie.languages = str(moviemeta['languages'])
        movie.plot = str(moviemeta['plot'])
        movie.runtimes = str(moviemeta['runtimes'])
        movie.year = int(moviemeta['year'])

        for p in moviemeta['cast']:
            self._add_person(p, movie, 'actor')
        for p in moviemeta['director']:
            self._add_person(p, movie, 'director')
        for p in moviemeta['producer']:
            self._add_person(p, movie, 'producer')
        for p in moviemeta['writer']:
            self._add_person(p, movie, 'writer')

        for c in moviemeta['distributor']:
            self._add_company(c, movie, 'distribution')
        for c in moviemeta['production companies']:
            self._add_company(c, movie, 'production')
        self._session.add(movie)
        self._session.commit()

    def add_to_show(self, vfids, showid=None, showimdbid=None):
        """
        Adds Videofiles as Episodes to a Show and optionally creates the show
        if it does not exist.
        """
        raise NotImplementedError

    #__________________________Private API_____________________________________
    def _setup_db(self, dbfile):
        engine = create_engine('sqlite:///' + dbfile)
        Base.metadata.bind = engine
        Base.metadata.create_all()
        self._session = Session()
        self._logger.debug("Connected to Database")


#    def _setup_fswatcher(self):
#        # Filesystem monitor
#        #TODO: ThreadedNotifier does not work with SQLite, use what instead?
#        self._wm = pyinotify.WatchManager()
#        self._notifier = pyinotify.ThreadedNotifier(self._wm,
#            self._EventHandler(self))
#        self._notifier.start()
#        self._logger.debug("Started filesystem monitoring")


    def _setup_imdb(self):
        self._imdb = imdb.IMDb()


#    class _EventHandler(pyinotify.ProcessEvent):
#        """
#        Handles events triggered by the pyinotify notifier.
#        """
#        def __init__(self, controller):
#            self._logger = logging.getLogger(
#                "kinoknecht.controller._EventHandler")
#            super(Controller._EventHandler, self).__init__()
#            self._controller = controller
#            self._fswatch_session = Session()
#
#        def process_IN_CLOSE_WRITE(self, event):
#            self._logger.debug("Created: %s" % event.pathname)
#            if not event.dir:
#                (fpath, fname) = os.path.split(event.pathname)
#                if fname.endswith(self._controller._ftypes_vid):
#                    self._controller._add_videofile(fpath, fname)
#                elif fname.endswith(self._controller._ftypes_sub):
#                    self._controller._add_subtitle(fpath, fname)
#
#        def process_IN_DELETE(self, event):
#            #TODO:  Query database for item with path and name and delete it
#            self._logger.debug("Deleted: %s" % event.pathname)
#             
#        def process_IN_MOVED_TO(self, event):
#            self._logger.debug("Moved to: %s" % event.pathname)
#            #TODO:  Query database for items with source path/name
#            #           exist -> update path/name
#            #           !exist -> call add_videofile


    def _scan_videodir(self, path):
        """
        Search recursively for supported video files.
        """
        #TODO:  Only collect files to be added and add them all at once to the
        #       db to improve performance
        self._logger.info(u"Scanning directory '%s' for video files" % path)
        vidtree = self._search_ftree(path, self._ftypes_vid)
        for viddir in vidtree.keys():
            for vidfile in vidtree[viddir]:
                # Does the file already exist in the db?
                dbentries = self._session.query(Videofile).filter_by(
                    name=to_unicode(vidfile))
                if not dbentries.count():
                    self._add_videofile(viddir, vidfile)
                    self._add_subtitle(viddir, vidfile)
                else:
                    # Seems like it, see if there's something to update
                    for vfobject in dbentries:
                        self._check_videofile(vfobject, viddir)
            # See if we have any related files in the current path
            # self._check_related_files(vidtree[viddir], viddir)
        self._session.commit()


#    def _add_watchdir(self, path):
#        """
#        Adds a directory to the watchlist.
#        """
#        # TODO: Verify that the directory or one of its parent directories are
#        #       not already being watched.
#        self._wm.add_watch(path, self._mask, rec=True)

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
            self._add_videofile(path, vfobject.name)


    def _check_related_files(self, flist, parentdir):
        """
        Checks if files are related (e.g. same movie split across different
        files, episodes from same season) and creates one or more VideoEntity
        objects with them if this is the case.
        """

        #FIXME: Looking at this code, I get a definitive feeling of
        #       gut-wrenching nausea... Yes, I am ashamed
        #TODO:  To improve performance, do this based on the database,
        #       not the filesystem
        relfiledict = {}
        for f in flist:
            # Match against all specified patterns
            for r in self._movie_regex_list + self._episode_regex_list:
                m = r.match(f)
                if m:
                    # We identify the group (and later the Entites and
                    # Collections) by their basename
                    basename = m.group('basename')
                    if not basename in relfiledict.keys():
                        relfiledict[basename] = {}
                        # Identify the file's media type (movie/tv-episode?)
                        if r in self._movie_regex_list:
                            relfiledict[basename]['type'] = 'movie'
                        elif r in self._episode_regex_list:
                            relfiledict[basename]['type'] = 'episode'
                        relfiledict[basename]['files'] = []
                    # Locate the files in the database and store them in our
                    # dictionary together with the properties extracted from
                    # the matches.
                    #TODO: Add some sanity checking here
                    vfid = self._session.query(Videofile).filter_by(
                        path=parentdir, name=f).one().id
                    filedict = { 'vfid': vfid,
                                 'props': m.groupdict() }
                    relfiledict[basename]['files'].append(filedict)
                    break

        for basename in relfiledict.keys():
            files = [x['vfid'] for x in relfiledict[basename]['files']]
            if relfiledict[basename]['type'] == 'movie':
                veobj = self._create_videoentity(basename, files)
                veobj.ve_type = 'movie'
                veobj.save()
            elif relfiledict[basename]['type'] == 'episode':
                eplist = []
                for ep in relfiledict[basename]['files']:
                    veobj = self._create_videoentity(basename, [ep['vfid']])
                    veobj.ve_type = 'episode'
                    veobj.episode = ep['props']['episode']
                    veobj.season = ep['props']['season']
                    veobj.save()
                    eplist.append(veobj.id)
                vcobj = self._create_videocollection(basename, eplist)
                vcobj.type = 'tvshow'
                vcobj.save()


    def _add_videofile(self, path, fname):
        """
        Add a Videofile object to database by getting data from the actual
        file on the harddisk.
        """
        fullpath = os.path.join(path, fname)
        specs = midentify(fullpath)
        if len(specs.keys) < 2:
            self._logger.error(u"%s is not a recognizable video file!" % fname)
            return
        vfobject = Videofile(
            name = to_unicode(fname),
            path = to_unicode(path),
            size = os.path.getsize(fullpath),
            creation_date = datetime.fromtimestamp(
                os.path.getctime(fullpath)),
            length = specs['length'],
            video_width = specs['video_width'],
            video_height = specs['video_height'],
            video_bitrate = specs['video_bitrate'],
            video_fps = specs['video_fps']
        )
        try:
            vfobject.video_format = str(specs['video_format'])
            vfobject.audio_bitrate = specs['audio_bitrate']
            vfobject.audio_format = str(specs['audio_format'])
        except KeyError:
            pass
        self._session.add(vfobject)
        self._logger.info(u"Added %s to database!" % fname)


    def _add_subtitle(self, path, vidname):
        """
        Search for subtitle files with the same name in the same directory
        and add it to the corresponding Videofile object.
        """
        #TODO: Generalize this to allow for more flexible subtitle search
        basename = os.path.splitext(vidname)[0]
        for f in os.listdir(path):
            (fname, fext) = os.path.splitext(f)
            fext = fext

            # Subtitles with the same basename as the corresponding videofile
            if fname == basename and fext in self._ftypes_sub:
                vfobj = self._session.query(Videofile).filter_by(
                    path=path, name=vidname).one()
                vfobj.subfilepath = os.path.join(path, f)
                self._session.add(vfobj)
                self._logger.info("Added subtitle for %s" % vfobj.name)
        self._session.commit()

    def _create_person(self, person):
        pobj = Person(person['canonical name'])
        pobj.imdbid = int(person.personID)
        self._session.add(pobj)
        return pobj

    def _add_person(self, person, movie, role):
        pobj = self._get_person(person['canonical name'])
        if not pobj:
            pobj = self._create_person(person)
        movie.persons.append(pobj)
        movie.persons[-1].movie_roles[-1].role = role


    def _get_person(self, name):
        try:
            return self._session.query(Person).filter_by(name=name).one()
        except NoResultFound:
            return None

    def _create_company(self, company):
        cobj = Company(company['name'])
        cobj.imdbid = int(company.companyID)
        self._session.add(cobj)
        return cobj

    def _add_company(self, company, movie, role):
        cobj = self._get_company(company['name'])
        if not cobj:
            cobj = self._create_company(company)
        movie.companies.append(cobj)
        movie.companies[-1].movie_roles[-1].role = role

    def _get_company(self, name):
        try:
            return self._session.query(Company).filter_by(name=name).one()
        except NoResultFound:
            return None


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
