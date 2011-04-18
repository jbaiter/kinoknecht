import os.path

from sqlalchemy import *
from sqlalchemy.orm import relationship, backref, scoped_session, sessionmaker, create_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy

Session = scoped_session(sessionmaker())
Base = declarative_base()

class Person(Base):
    """
    Represents a person involved in Movies, Episodes and Shows
    """
    __tablename__ = 'persons'

    id = Column(Integer, primary_key=True)
    imdbid = Column(Integer)
    name = Column(Unicode)
    birth_date = Column(DateTime)
    death_date = Column(DateTime)
    biography = Column(Text)
    quotes = Column(Text)
    movies = association_proxy('movie_roles', 'movie',
        creator=lambda m: PersonMovieRole(movie=m))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<Person %d, %s>" % (self.id, self.name)

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

    def __repr__(self):
        return "<PersonMovieRole(%s, %d, %d)>" % (role, person_id, movie_id)

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

class Company(Base):
    """
    Represents a company involved in the production and/or distribution
    of a Movie, Episode or Show
    """
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True)
    imdbid = Column(Integer)
    name = Column(Unicode)
    country = Column(Unicode)
    movies = association_proxy('movie_roles', 'movie',
        creator=lambda m: CompanyMovieRole(movie=m))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<Company %d, %s>" % (self.id, self.name)


class MetadataMixin(object):
    """
    Metadata specific to either VideoEntity or VideoCollection objects.
    """

    id = Column(Integer, primary_key=True)
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


class Videofile(Base):
    """
    Represents a single file on the filesystem and all the data specific to it
    """
    __tablename__ = 'videofiles'

    id = Column(Integer, primary_key=True)
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

    def __init__(self, name, path, size, creation_date, length, video_width,
        video_height, video_bitrate, video_fps):
        self.name = name
        self.path = path
        self.size = size
        self.creation_date = creation_date
        self.length = length
        self.video_width = video_width
        self.video_height = video_height
        self.video_bitrate = video_bitrate
        self.video_fps = video_fps

    def __repr__(self):
        return "<Videofile('%s', '%s')>" % (self.name, self.path)


episodes_videofiles = Table(
    'episodes_videofiles', Base.metadata,
    Column('episode_id', Integer, ForeignKey('episodes.id')),
    Column('videofile_id', Integer, ForeignKey('videofiles.id'))
    )

class Episode(Base, MetadataMixin):
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


class Show(Base, MetadataMixin):
    """ Show object """
    __tablename__ = 'shows'

    id = Column(Integer, primary_key=True)
    years = Column(String)
    episodes = relationship("Episode", backref='show')
    show_type = Column(String)
    complete_num_episodes = Column(Integer)


movies_videofiles = Table(
    'movies_videofiles', Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id')),
    Column('videofile_id', Integer, ForeignKey('videofiles.id'))
    )

class Movie(Base, MetadataMixin):
    """ Movie object """
    __tablename__ = 'movies'

    id = Column(Integer, primary_key=True)
    videofiles = relationship("Videofile", secondary=movies_videofiles)
    title = Column(Unicode)
    year = Column(Integer)
    persons = association_proxy('persons_roles', 'person',
        creator=lambda p: PersonMovieRole(person=p))
    companies = association_proxy('companies_roles', 'company',
        creator=lambda c: CompanyMovieRole(company=c))
