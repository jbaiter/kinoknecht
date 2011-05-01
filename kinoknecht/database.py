import os
import re
import logging
from datetime import datetime
from mimetypes import types_map

import imdb
from sqlalchemy import (Table, Column, Integer, Enum, Float, ForeignKey,
                        String, Unicode, Text, DateTime, create_engine, and_)
from sqlalchemy.orm import relationship, scoped_session, sessionmaker, synonym
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.ext.associationproxy import association_proxy

import config
from kinoknecht.midentify import midentify


imdb = imdb.IMDb()
logger = logging.getLogger("model")

Session = scoped_session(sessionmaker())
global_session = Session()
Base = declarative_base()

def setup_db():
    """ Sets up the database according to the configuration in config.py """
    dbfile = os.path.abspath(config.db_file)
    engine = create_engine('sqlite:///' + dbfile)
    logger.debug('Database configured for %s' % config.db_file)
    Base.metadata.bind = engine
    Base.metadata.create_all()
    logger.debug('Database successfuly set up!')

def destroy_db():
    """ Closes all sessions and unbinds the engine """
    Session.close_all()
    Base.metadata.bind = None

def to_unicode(string):
    """ Force unicode on string"""
    #TODO: This smells, there must be a more proper way to do this
    #TODO: Move this to a 'util'/'helpers' module
    if not isinstance(string, unicode):
        try:
            return unicode(string)
        except UnicodeDecodeError:
            return unicode(string, errors='replace')
    else:
        return string


class KinoBase(object):
    """ Base class for all of our publicly accessible data types. """

    _session = global_session
    id = Column(Integer, primary_key=True)

    @classmethod
    def get(cls, id):
        return cls._session.query(cls).get(id)

    @classmethod
    def search(cls, *sparams):
        if not sparams:
            return cls._session.query(cls)
        if len(sparams) > 1:
            squery = and_(*sparams)
        else:
            squery = sparams[0]
        return cls._session.query(cls).filter(squery)

    @classmethod
    def list(cls):
        return cls._session.query(cls).all()

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


class Person(Base, KinoBase):
    """
    Represents a person involved in Movies, Episodes and Shows
    """
    __tablename__ = 'persons'

    imdb_id = Column(Integer, unique=True)
    name = Column(Unicode)
    birth_date = Column(String)
    death_date = Column(String)
    biography = Column(Text)
    quotes = Column(Text)
    movies = association_proxy('movie_roles', 'movie',
        creator=lambda m: PersonMovieRole(movie=m))
    episodes = association_proxy('episode_roles', 'episode',
        creator=lambda e: PersonEpisodeRole(episode=e))

    def __init__(self, name, imdbid):
        self.name = name
        self.imdb_id = imdbid

    def __repr__(self):
        return "<Person %d, %s>" % (self.id, self.name)

    def update_info(self):
        meta = imdb.get_person(self.imdb_id)
        imdb.update(meta)
        self.birth_date = int(meta['birth date'])
        if 'death date' in meta.keys():
            self.death_date = meta['death date']
        if 'mini biography' in meta.keys():
            self.biography = str(meta['mini biography'])
        if 'quotes' in meta.keys():
            self.quotes = str(meta['quotes'])


class PersonMovieRole(Base):
    """ Role for a Person in a Movie. """
    __tablename__ = 'persons_movies'

    id = Column(Integer, primary_key=True)
    role = Column(Enum('none', 'actor', 'writer', 'director', 'producer'),
        default='none')
    person_id = Column(Integer, ForeignKey('persons.id'))
    person = relationship('Person', backref='movie_roles')
    movie_id = Column(Integer, ForeignKey('movies.id'))
#    movie = relationship('Movie', backref='persons_roles')
    movie = relationship('Movie')

    def __init__(self, movie=None, person=None):
        self.movie = movie
        self.person = person


class PersonEpisodeRole(Base):
    """ Role for a Person in an Episode. """
    __tablename__ = 'persons_episodes'

    id = Column(Integer, primary_key=True)
    role = Column(Enum('none', 'actor', 'writer', 'director', 'producer'),
        default='none')
    person_id = Column(Integer, ForeignKey('persons.id'))
    person = relationship('Person', backref='episode_roles')
    episode_id = Column(Integer, ForeignKey('episodes.id'))
#    episode = relationship('Episode', backref='persons_roles')
    episode = relationship('Episode')

    def __init__(self, episode=None, person=None):
        self.episode = episode
        self.person = person


class Company(Base):
    """ Represents a company involved in the production and/or distribution
    of a Movie, Episode or Show.
    """
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(Integer, unique=True)
    name = Column(Unicode)
    country = Column(Unicode)
    movies = association_proxy('movie_roles', 'movie',
        creator=lambda m: CompanyMovieRole(movie=m))

    def __init__(self, name, imdbid):
        self.name = name
        self.imdb_id = imdbid

    def __repr__(self):
        return "<Company %d, %s>" % (self.id, self.name)

    def update_info(self):
        meta = imdb.get_company(self.imdb_id)
        imdb.update(meta)
        self.birth_date = int(meta['birth date'])
        if 'country' in meta.keys():
            self.country = str(meta['death date'])


class CompanyMovieRole(Base):
    """ Role for a Company in a Movie. """
    __tablename__ = 'companies_movies'

    id = Column(Integer, primary_key=True)
    role = Column(Enum('none', 'production', 'distribution'), default='none')
    company_id = Column(Integer, ForeignKey('companies.id'))
    company = relationship('Company', backref='movie_roles')
    movie_id = Column(Integer, ForeignKey('movies.id'))
    movie = relationship('Movie', backref='companies_roles')

    def __init__(self, movie=None, company=None):
        self.movie = movie
        self.company = company


class CompanyEpisodeRole(Base):
    """ Role for a Company in an Episode. """
    __tablename__ = 'companies_episodes'

    id = Column(Integer, primary_key=True)
    role = Column(Enum('none', 'production', 'distribution'), default='none')
    company_id = Column(Integer, ForeignKey('companies.id'))
    company = relationship('Company', backref='episode_roles')
    episode_id = Column(Integer, ForeignKey('episodes.id'))
    episode = relationship('Episode', backref='companies_roles')

    def __init__(self, episode=None, company=None):
        self.episode = episode
        self.company = company


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

    @declared_attr
    def persons_roles(cls):
        if cls.__name__ == 'Movie':
            return relationship('PersonMovieRole')
        elif cls.__name__ == 'Episode':
            return relationship('PersonEpisodeRole')
        else:
            return None

    @declared_attr
    def persons(cls):
        if cls.__name__ == 'Episode':
            return association_proxy('persons_roles', 'person',
                                creator=lambda p: PersonEpisodeRole(person=p))
        elif cls.__name__ == 'Movie':
            return association_proxy('persons_roles', 'person',
                                creator=lambda p: PersonMovieRole(person=p))
        else:
            return None

    @declared_attr
    def companies(cls):
        if cls.__name__ == 'Episode':
            return association_proxy('companies_roles', 'company',
                            creator=lambda c: CompanyEpisodeRole(company=c))
        elif cls.__name__ == 'Movie':
            return association_proxy('companies_roles', 'company',
                            creator=lambda c: CompanyMovieRole(company=c))
        else:
            return None

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

        # Role descriptions from IMDbPy mapped to their equivalent in
        # our schema
        personmap = {
            'cast': 'actor',
            'director': 'director',
            'producer': 'producer',
            'writer': 'writer'
        }
        companymap = {
            'distributor': 'distribution',
            'production companies': 'production'
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

        for rolekey in personmap.keys():
            try:
                for p in meta[rolekey]:
                    self._add_person(p, personmap[rolekey])
            except KeyError:
                pass

        for rolekey in companymap.keys():
            try:
                for c in meta[rolekey]:
                    self._add_company(c, companymap[rolekey])
            except KeyError:
                pass

    def _create_person(self, person):
        pobj = Person(person['canonical name'], person.personID)
        self._session.add(pobj)
        return pobj

    def _add_person(self, person, role):
        pobj = self._get_person(person.personID)
        if not pobj:
            pobj = self._create_person(person)
        self.persons.append(pobj)
        self.persons[-1].movie_roles[-1].role = role

    def _get_person(self, imdbid):
        try:
            return self._session.query(Person).filter_by(imdb_id=imdbid).one()
        except NoResultFound:
            return None

    def _create_company(self, company):
        cobj = Company(company['name'], company.companyID)
        self._session.add(cobj)
        return cobj

    def _add_company(self, company, role):
        cobj = self._get_company(company.companyID)
        if not cobj:
            cobj = self._create_company(company)
        self.companies.append(cobj)
        self.companies[-1].movie_roles[-1].role = role

    def _get_company(self, imdbid):
        try:
            return self._session.query(Company).filter_by(imdb_id=imdbid).one()
        except NoResultFound:
            return None


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

        qresult = cls._session.query(cls).filter(
            cls.path.like('%' + path + '%'))
        # Get subdirs
        subdirs = []
        for i in qresult:
            splitpath = os.path.split(i.path)
            if splitpath[0] == path and i.path not in subdirs:
                subdirs.append(i.path)
        # Get videofiles
        vfiles = [vfile for vfile in
                  cls._session.query(Videofile).filter_by(path=path)]
        return [subdirs, vfiles]

    @classmethod
    def update_all(cls):
        for vdir in cls.videodirs:
            cls.update_files(vdir)

    @classmethod
    def statistics(cls):
        statdict = {}
        statdict['total_size'] = sum([x.size for x in
                                      cls._session.query(Videofile)])
        statdict['total_length'] = sum([x.length for x in
                                       cls._session.query(Videofile)])
        statdict['vidfile_count'] = cls._session.query(Videofile).count()
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
                dbentries = cls._session.query(Videofile).filter_by(
                    name=to_unicode(vidfile))
                if not dbentries.count():
                    vfobj = Videofile(viddir, vidfile)
                    vfobj.find_subtitle()
                    scanobjs.append(vfobj)
                else:
                    # Seems like it, see if there's something to update
                    for vfobj in dbentries:
                        vfobj._check_path(viddir)
        cls._session.add_all(scanobjs)
        cls._session.commit()
        Movie.find_multifile_movies(*scanobjs)
        Episode.find_episodes(*scanobjs)

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
        for root, dirs, files in os.walk(to_unicode(path)):
            matchlist = []
            for name in files:
                if name.endswith(ftypes):
                    matchlist.append(name)
            if len(matchlist) > 0:
                filedict[root] = matchlist
        return filedict

    def __init__(self, path, fname):
        fullpath = os.path.join(path, fname)
        specs = midentify(fullpath)
        if len(specs.keys) < 2:
            logger.error(u"%s is not a recognizable video file!" % fname)
            raise IOError(u"%s not a recognizable video file!" % fname)

        self.name = to_unicode(fname)
        self.path = to_unicode(path)
        self.size = os.path.getsize(fullpath)
        self.creation_date = datetime.fromtimestamp(
            os.path.getctime(fullpath))
        self.length = specs['length']
        self.video_width = specs['video_width']
        self.video_height = specs['video_height']
        self.video_bitrate = specs['video_bitrate']
        self.video_fps = specs['video_fps']

        try:
            self.video_format = str(specs['video_format'])
            self.audio_bitrate = specs['audio_bitrate']
            self.audio_format = str(specs['audio_format'])
        except KeyError:
            pass
        logger.info(u"Added %s to database!" % fname)

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
            self._logger.info(u"Updated video file %s" % self.name)
        else:
            # Seems we have a duplicate!
            self._logger.warning(u"File with name '%s' already exists in"
                "the database, might be a duplicate!" % self.name)
            new_vfobj = Videofile(path, self.name)
            self._session.add(new_vfobj)

    def find_subtitle(self):
        """ Find subtitle files for the Videofile. """
        ftypes = ('.srt', '.ass', '.sub')
        # Subtitles with the same basename as the corresponding videofile
        basename = os.path.splitext(self.name)[0]
        for f in os.listdir(self.path):
            (fname, fext) = os.path.splitext(f)
            if fname == basename and fext in ftypes:
                self.subfilepath = os.path.join(self.path, f)
                logger.info("Added subtitle for %s" % self.name)

    

episodes_videofiles = Table(
    'episodes_videofiles', Base.metadata,
    Column('episode_id', Integer, ForeignKey('episodes.id')),
    Column('videofile_id', Integer, ForeignKey('videofiles.id'))
    )


class Episode(Base, KinoBase, MetadataMixin):
    """ Episode object """
    __tablename__ = 'episodes'

    id = Column(Integer, primary_key=True)
    season_num = Column(Integer, nullable=True)
    episode_num = Column(Integer)
    year = Column(Integer)
    videofiles = relationship('Videofile', secondary=episodes_videofiles)
    show_id = Column(Integer, ForeignKey('shows.id'))

    @classmethod
    def find_episodes(cls, *videofiles):
        """ Finds episodes among videofiles (all if none specified) and
        creates Episode and Show objects for them.
        """
        rexps = [
            re.compile(
        r'(?P<basename>.*)(?:S(?P<season>\d+)E(?P<episode>\d+)).*', re.I),
            re.compile(
        r'(?P<basename>.*)(?P<season>\d)(?P<episode>\d{2,3}).*', re.I)
        ]
        
        if not videofiles:
            videofiles = cls._session.query(Videofile)
        for vf in videofiles:
            m = None
            for r in rexps:
                m = r.match(vf.name)
                if m:
                    break
            if not m:
                break
            basename = m.group('basename')
            season_num = m.group('season')
            episode_num = m.group('episode')
            query = cls._session.query(Show).filter_by(basename=basename)
            if query.count() != 1:
                show = cls.create_show(basename)
                cls._session.add(show)
            else:
                show = query.one()
            episode = Episode(season_num, episode_num, show)
            show.episodes.append(episode)
            cls._session.add(episode)
        cls._session.commit()

    def __init__(self, season_num, episode_num, show):
        self.season_num = season_num
        self.episode_num = episode_num
        self.show_id = show.id
        if show.imdb_id:
            show_episodes = self._imdb.get_movie_episodes(show.imdb_id)
            self.imdb_id = show_episodes['data']['episodes'][int(
                season_num)][int(episode_num)].movieID
            self.update_metadata()

    def __repr__(self):
        return "<Episode('%d', '%d')>" % (self.episode_num, self.videofile_id)


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


movies_videofiles = Table(
    'movies_videofiles', Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id')),
    Column('videofile_id', Integer, ForeignKey('videofiles.id'))
    )


class Movie(Base, KinoBase, MetadataMixin):
    """ Movie object """
    __tablename__ = 'movies'

    videofiles = relationship("Videofile", secondary=movies_videofiles)
    title = Column(Unicode)
    year = Column(Integer)

    @classmethod
    def find_multifile_movies(cls, *videofiles):
        """ Finds movies that are split across several CDs/DVDs among 
        Videofile objects (all if none specified) and creates Movie objects
        for them.
        """
        regexps = [
            re.compile(
            r'(?P<basename>.*)(?P<num>\d+) *of *(?:\d+).*', re.I),
            re.compile(
                r'(?P<basename>.*)(?:CD|DVD|Disc|Part) *(?P<num>\d+).*', re.I)
            ]
        
        if not videofiles:
            videofiles = cls._session.query(Videofile)
        # Find all related files among videofiles
        relfiledict = {}
        for vf in videofiles:
            m = None
            for r in regexps:
                m = r.match(vf.name)
                if m:
                    break
            if not m:
                break
            try:
                basename = m.group('basename')
            # This means the files are named like 'cd1.avi', etc, so we
            # try to derive the basename from the parent directory
            except:
                basename = os.path.basename(vf.path)
            if not basename in relfiledict.keys():
                relfiledict[basename] = [vf]
            else:
                relfiledict[basename].append(vf)

        # Create Movies for the files
        for (basename, files) in relfiledict.iteritems():
            #TODO: Query IMDb with basename as query to find metadata?
            mov = Movie(videofiles=files, title=basename)
            cls._session.add(mov)


