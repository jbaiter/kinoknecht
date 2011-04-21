import os
import logging
from datetime import datetime

import imdb
from sqlalchemy import (Table, Column, Integer, Float, ForeignKey, Enum,
                        String, Unicode, Text, DateTime)
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy

from kinoknecht.midentify import midentify

Session = scoped_session(sessionmaker())
Base = declarative_base()

imdb = imdb.IMDb()
logger = logging.getLogger("model")


def to_unicode(string):
    """
    Force unicode on string
    """
    #TODO: This smells, there must be a more proper way to do this
    if not isinstance(string, unicode):
        try:
            return unicode(string)
        except UnicodeDecodeError:
            return unicode(string, errors='replace')
    else:
        return string


class KinoBase():
    """
    Base class for all of our data types.
    """

    _session = Session()
    id = Column(Integer, primary_key=True)

    def get_infodict(self, *keys):
        """
        Return dictionary with values for all specified keys, or all public
        fields if no keys are specified.
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

    def __init__(self, name, imdbid):
        self.name = name
        self.imdb_id = imdbid

    def __repr__(self):
        return "<Person %d, %s>" % (self.id, self.name)

    def update_info(self):
        meta = i.get_person(self.imdb_id)
        i.update(meta)
        self.birth_date = int(meta['birth date'])
        if 'death date' in meta.keys():
            self.death_date = meta['death date']
        if 'mini biography' in meta.keys():
            self.biography = str(meta['mini biography'])
        if 'quotes' in meta.keys():
            self.quotes = str(meta['quotes'])


class PersonMovieRole(Base):
    """
    Role for a Person in a Movie
    """
    __tablename__ = 'persons_movies'

    id = Column(Integer, primary_key=True)
    role = Column(Enum('none', 'actor', 'writer', 'director', 'producer'),
        default='none')
    person_id = Column(Integer, ForeignKey('persons.id'))
    person = relationship('Person', backref='movie_roles')
    movie_id = Column(Integer, ForeignKey('movies.id'))
    movie = relationship('Movie', backref='persons_roles')

    def __init__(self, movie=None, person=None):
        self.movie = movie
        self.person = person


class PersonEpisodeRole(Base):
    """
    Role for a Person in an Episode
    """
    __tablename__ = 'persons_episodes'

    id = Column(Integer, primary_key=True)
    role = Column(Enum('none', 'actor', 'writer', 'director', 'producer'),
        default='none')
    person_id = Column(Integer, ForeignKey('persons.id'))
    person = relationship('Person', backref='episode_roles')
    episode_id = Column(Integer, ForeignKey('episodes.id'))
    episode = relationship('Episode', backref='persons_roles')

    def __init__(self, episode=None, person=None):
        self.episode = episode
        self.person = person


class CompanyMovieRole(Base):
    """
    Role for a Company in a Movie
    """
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
    """
    Role for a Company in an Episode
    """
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


class Company(Base):
    """
    Represents a company involved in the production and/or distribution
    of a Movie, Episode or Show
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
        meta = i.get_company(self.imdb_id)
        i.update(meta)
        self.birth_date = int(meta['birth date'])
        if 'country' in meta.keys():
            self.country = str(meta['death date'])


class MetadataMixin(object):
    """
    Metadata specific to either VideoEntity or VideoCollection objects.
    """

    imdb_id = Column(Integer)
    imdb_rating = Column(Float)
    imdb_genres = Column(Unicode)
    cover_url = Column(String)
    title = Column(Unicode)
    plot = Column(Text)
    alt_titles = Column(Unicode)
    languages = Column(Unicode)
    runtimes = Column(Unicode)
    color_info = Column(Unicode)

    def update_metadata(self):
        """
        Updates the metadata of the object from imdb, using its imdb_id
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
    """
    Represents a single file on the filesystem and all the data specific to it
    """
    __tablename__ = 'videofiles'
    __table_args__ = (
        UniqueConstraint('name', 'path'),
        {}
    )

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

    def find_subtitle(self):
        """
        Find subtitle files for the Videofile.
        """
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
    persons = association_proxy('persons_roles', 'person',
        creator=lambda p: PersonMovieRole(person=p))
    companies = association_proxy('companies_roles', 'company',
        creator=lambda c: CompanyMovieRole(company=c))
