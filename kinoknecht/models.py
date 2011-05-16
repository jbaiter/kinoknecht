import os
import re
import logging
import pdb
from datetime import datetime
from mimetypes import types_map

import imdb
from sqlalchemy import (Table, Column, Integer, Float, ForeignKey,
                        String, Unicode, Text, DateTime, and_)
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declared_attr

import config
from kinoknecht.midentify import midentify
from kinoknecht.database import Base, db_session
from kinoknecht.helpers import to_unicode

imdb = imdb.IMDb()
logger = logging.getLogger("kinoknecht.models")


class KinoBase(object):
    """ Base class for all of our publicly accessible data types. """

    id = Column(Integer, primary_key=True)

    @classmethod
    def get(cls, id):
        return cls.query.get(id)

    @classmethod
    def search(cls, *sparams):
        if not sparams:
            return cls.query
        if len(sparams) > 1:
            squery = and_(*sparams)
        else:
            squery = sparams[0]
        return cls.query.filter(squery)

    @classmethod
    def statistics(cls):
        """ Returns a dictionary with statistics.
        Needs to be implemented by every subclass itself.
        """
        raise NotImplementedError("This should have been implemented!")

    def get_infodict(self, *keys):
        """ Return dictionary with values for all specified keys, or all
        public fields if no keys are specified.
        """
        if not keys:
            keys = self.__dict__.keys()
        for key in keys:
            if key not in self.__dict__.keys():
                raise KeyError
        return dict(
            (k, v) for (k, v) in self.__dict__.iteritems()
            if not k.startswith('_') and k in keys
            )


class MetadataMixin(object):
    """ Metadata specific to either VideoEntity or VideoCollection objects."""

    imdb_rating = Column(Float)
    imdb_genres = Column(Unicode)
    cover_url = Column(String)
    title = Column(Unicode)
    plot = Column(Text)
    alt_titles = Column(Unicode)
    languages = Column(Unicode)
    runtimes = Column(Unicode)
    color_info = Column(Unicode)

    _imdb_id = Column('imdb_id', Integer)

    def imdbid_getter(self):
        return self._imdb_id

    def imdbid_setter(self, imdbid):
        self._imdb_id = imdbid
        self.update_metadata()

    @declared_attr
    def imdb_id(cls):
        return synonym('_imdb_id', descriptor=property(
            cls.imdbid_getter, cls.imdbid_setter))

    def update_metadata(self):
        """ Updates the metadata of the object from imdb, using its imdb_id
        attribute.
        """
        if not self.imdb_id:
            raise ValueError('self.imdb_id is not specified!')
        meta = imdb.get_movie(self.imdb_id)
        imdb.update(meta)

        # Fields that are named differently than in the IMDbPy object
        imdbmap = {
            'smart canonical title': 'title',
            'color info': 'color_info',
            'akas': 'alt_titles',
            'full-size cover url': 'cover_url'
        }

        for imdbkey in meta.keys():
            if hasattr(self, imdbkey):
                # If the field is an iterable, we store its string
                # representation which we can eval() for retrieval later on.
                #FIXME: This is a *HUGE* security hole as it allows the
                #       execution of arbitrary code, maybe pickeling would
                #       be a better choice (would it really?)
                if getattr(meta[imdbkey], '__iter__', False):
                    meta[imdbkey] = to_unicode(meta[imdbkey])

                # We want to store 'year' as an Integer to allow for better
                # sorting.
                if imdbkey == 'year':
                    meta[imdbkey] = int(meta[imdbkey])
                setattr(self, imdbkey, meta[imdbkey])
            elif imdbkey in imdbmap.keys():
                if getattr(meta[imdbkey], '__iter__', False):
                    meta[imdbkey] = to_unicode(meta[imdbkey])
                setattr(self, imdbmap[imdbkey], meta[imdbkey])


class Videofile(Base, KinoBase):
    """ Represents a single file on the filesystem and all the data specific
    to it """
    __tablename__ = 'videofiles'
    __table_args__ = (
        UniqueConstraint('name', 'path'),
        {}
    )

    videodirs = config.video_dirs

    name = Column(Unicode)
    path = Column(Unicode)
    size = Column(Integer)
    creation_date = Column(DateTime)

    length = Column(Float)
    video_width = Column(Integer)
    video_height = Column(Integer)
    video_format = Column(Unicode, nullable=True)
    video_bitrate = Column(Integer)
    video_fps = Column(Float)
    audio_format = Column(Unicode, nullable=True)
    audio_bitrate = Column(Integer)

    playeropts = Column(Unicode, nullable=True)
    subfilepath = Column(Unicode, nullable=True)

    num_played = Column(Integer, nullable=True)
    last_pos = Column(Integer, nullable=True)

    @classmethod
    def browse(cls, path=None):
        # Return list of root-level video directories (as specified in config)
        if not path:
            return [[x for x in cls.videodirs], []]

        qresult = cls.query.filter(
            cls.path.like('%' + path + '%'))
        # Get subdirs
        subdirs = []
        for i in qresult:
            splitpath = os.path.split(i.path)
            if splitpath[0] == path and i.path not in subdirs:
                subdirs.append(i.path)
        # Get videofiles
        vfiles = [vfile for vfile in
                  cls.query.filter_by(path=path)]
        return [subdirs, vfiles]

    @classmethod
    def update_all(cls):
        for vdir in cls.videodirs:
            cls.update_files(vdir)

    @classmethod
    def statistics(cls):
        statdict = {}
        statdict['total_size'] = sum([x.size for x in cls.query])
        statdict['total_length'] = sum([x.length for x in cls.query])
        statdict['vidfile_count'] = cls.query.count()
        return statdict

    @classmethod
    def update_files(cls, path):
        """ Search recursively in path for supported video files. """
        logger.info(u"Scanning directory '%s' for video files" % path)
        scanobjs = []
        vidtree = cls._find_videofiles(path)
        for viddir in vidtree.keys():
            for vidfile in vidtree[viddir]:
                # Does the file already exist in the db?
                logger.debug('Checking file %s' % unicode(vidfile))
                logger.debug('Size: %d' % os.path.getsize(os.path.join(
                    viddir, vidfile)))
                dbentries = cls.query.filter_by(name=unicode(vidfile),
                        size=os.path.getsize(os.path.join(viddir, vidfile)))
                if not dbentries.count():
                    try:
                        vfobj = Videofile(os.path.abspath(viddir), vidfile)
                        vfobj.find_subtitle()
                        scanobjs.append(vfobj)
                    except IOError as e:
                        logger.error(e)
                else:
                    # Seems like it, see if there's something to update
                    # like it, see if there's something to update
                    for vfobj in dbentries:
                        vfobj._check_path(os.path.abspath(viddir))
        db_session.add_all(scanobjs)
        db_session.commit()

    @classmethod
    def _find_videofiles(cls, path):
        """ Walk the filetree to find videofiles """
        # Get video filetypes from the MIME database and add some own ones
        ftypes = [k for (k, v) in types_map.iteritems() if 'video' in v]
        ftypes = tuple(ftypes + [i for i in
                               ['.wmv', '.flv', '.mkv', '.rm', '.m2v']
                               if i not in ftypes
                              ])
        filedict = {}
#        for root, dirs, files in os.walk(to_unicode(path)):
        for root, dirs, files in os.walk(unicode(path)):
            matchlist = []
            for name in files:
                if name.endswith(ftypes):
                    matchlist.append(name)
            if len(matchlist) > 0:
                filedict[root] = matchlist
        return filedict

    def __init__(self, path, fname):
        path = os.path.abspath(path)
        fullpath = os.path.join(path, fname)
        specs = midentify(fullpath)
        if len(specs.keys) < 2:
            logger.error(u"%s is not a recognizable video file!" % fname)
            raise IOError(u"%s not a recognizable video file!" % fname)

        self.name = unicode(fname)
        self.path = unicode(path)
        self.size = os.path.getsize(fullpath)
        self.creation_date = datetime.fromtimestamp(
            os.path.getctime(fullpath))
        self.length = specs['length']
        self.video_width = specs['video_width']
        self.video_height = specs['video_height']
        self.video_bitrate = specs['video_bitrate']
        self.video_fps = specs['video_fps']

        try:
            self.video_format = unicode(specs['video_format'])
            self.audio_bitrate = specs['audio_bitrate']
            self.audio_format = unicode(specs['audio_format'])
        except KeyError:
            pass
        logger.info(u"Added %s to database!" % to_unicode(fname))

    def __repr__(self):
        return "<Videofile('%s', '%s')>" % (self.name, self.path)

    def _check_path(self, path):
        """ Checks if the Videofile exists in the specified path and if its
        own path correlates with it. Updates the Videofile or creates a new
        one.
        """
        if path == self.path:
            # Nothing to update here!
            return
        if not os.path.exists(os.path.join(self.path, self.name)):
            self.path = path
            logger.info(u"Updated video file %s" % self.name)
        else:
            # Seems we have a duplicate!
            if Videofile.query.filter_by(name=self.name, path=path).count():
                logger.error(u"File at '%s' already exists in"
                "the database, might be a duplicate, will not be added!"
                % os.path.join(path, self.name))
                return
            try:
                new_vfobj = Videofile(path, self.name)
            except IOError as e:
                logger.error(e)
            db_session.add(new_vfobj)
            db_session.commit()

    def find_subtitle(self):
        """ Find subtitle files for the Videofile. """
        ftypes = ('.srt', '.ass', '.sub')
        # Subtitles with the same basename as the corresponding videofile
        basename = os.path.splitext(self.name)[0]
        for f in os.listdir(self.path):
            (fname, fext) = os.path.splitext(f)
            if fname == basename and fext in ftypes:
                self.subfilepath = os.path.join(self.path, f)
                logger.info("Added subtitle for %s" % to_unicode(self.name))


class Show(Base, KinoBase, MetadataMixin):
    """ Show object """
    __tablename__ = 'shows'

    id = Column(Integer, primary_key=True)
    years = Column(String)
    episodes = relationship("Episode", backref='show')
    show_type = Column(String)
    complete_num_episodes = Column(Integer)
    #FIXME: This is a rather ugly solution....
    basename = Column(Unicode)

    def __init__(self, imdbid=None, basename=None):
        if basename:
            self.basename = basename
        if imdbid:
            self.imdb_id = imdbid
            self.update_metadata()


episodes_videofiles = Table(
    'episodes_videofiles', Base.metadata,
    Column('episode_id', Integer, ForeignKey('episodes.id')),
    Column('videofile_id', Integer, ForeignKey('videofiles.id'),
           primary_key=True)
    )


class Episode(Base, KinoBase, MetadataMixin):
    """ Episode object """
    __tablename__ = 'episodes'

    id = Column(Integer, primary_key=True)
    season_num = Column(Integer, nullable=True)
    episode_num = Column(Integer)
    year = Column(Integer)
    videofiles = relationship('Videofile', secondary=episodes_videofiles,
                              backref='episode')
    show_id = Column(Integer, ForeignKey('shows.id'))

    def __init__(self, vfile):
        #TODO: Make regexps more robust, eg for tp02.avi (S0E2),
        #      skins1x07 (S1E7), skins_s1_e8 (S1E8),
        #      seinfeld.7x17.the_doll.avi, files without any season/episode
        rexps = [
            re.compile(
        r'(?P<basename>.*)(?:S(?P<season>\d+)E(?P<episode>\d+)).*', re.I),
            re.compile(
        r'(?P<basename>.*)(?P<season>\d)(?P<episode>\d{2,3}).*', re.I),
            re.compile(
        r'(?P<basename>.*)(?P<season>\d+)x(?P<episode>\d+).*', re.I)
        ]
        for r in rexps:
            m = r.match(vfile.name)
            if m:
                break
        if m:
            season_num = m.group('season')
            episode_num = m.group('episode')
            if season_num: self.season_num = season_num
            if episode_num: self.episode_num = episode_num
        self.videofiles.append(vfile)

    def __repr__(self):
        return "<Episode('%d', '%d')>" % (self.episode_num, self.videofile_id)

    def get_meta_from_show(self):
        show_episodes = self._imdb.get_movie_episodes(show.imdb_id)
        self.imdb_id = (show_episodes['data']['episodes'][int(self.season_num)]
                        [int(self.episode_num)].movieID)
        self.update_metadata()


movies_videofiles = Table(
    'movies_videofiles', Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id')),
    Column('videofile_id', Integer, ForeignKey('videofiles.id'))
    )


class Movie(Base, KinoBase, MetadataMixin):
    """ Movie object """
    __tablename__ = 'movies'

    videofiles = relationship("Videofile", secondary=movies_videofiles,
                              backref='movie')
    title = Column(Unicode)
    year = Column(Integer)
