from __future__ import absolute_import

from sqlalchemy import and_, desc
from flask import Flask, render_template
from flaskext.sqlalchemy import Pagination

from kinoknecht.models import Videofile, CATEGORIES_CLASSES


CATEGORIES_BROWSETEMPLATES = {'file': 'browse_files.html',
                              'movie': 'browse_movies.html',
                              'show': 'browse_shows.html',
                              'unassigned': 'browse_files.html'}
CATEGORIES_DETAILSTEMPLATES = {'file': 'details_file.html',
                               'movie': 'details_movie.html',
                               'show': 'details_show.html',
                               'episode': 'details_episode.html'}
PER_PAGE = 25

kinowebapp = Flask(__name__)

def get_page_startitem(page):
    return page * PER_PAGE - PER_PAGE

def get_page_enditem(page):
    return page * PER_PAGE

@kinowebapp.template_filter('humansize')
def humansize_filter(s):
    """Converts sizes from bytes to a human readable format"""
    num = int(s)
    for x in ['bytes','KB','MB','GB','TB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0

@kinowebapp.template_filter('humanduration')
def humanduration_filter(s):
    """Converts durations from seconds to a human readable format"""
    if not s:
        return "?h?m?s"
    basetime = float(s)
    hours = basetime//3600
    minutes = (basetime%3600)//60
    seconds = basetime - (hours*3600 + minutes*60)
    try:
        return "%d:%0*d:%0*d" % (hours, 2, minutes, 2, seconds)
    except TypeError:
        return "?:?:?"


@kinowebapp.route('/')
def index():
    return render_template('index.html')


@kinowebapp.route('/browse/')
@kinowebapp.route('/browse/<category>')
@kinowebapp.route('/browse/<category>/<int:page>')
def browse(page=1, category='file'):
    if category not in CATEGORIES_CLASSES:
        return ""

    elif category == 'unassigned':
        query = Videofile.query.filter(and_(Videofile.episode == None,
                                              Videofile.movie == None))
        results = (query.order_by(desc(Videofile.creation_date))
                  [get_page_startitem(page): get_page_enditem(page)])
    else:
        dbclass = CATEGORIES_CLASSES[category]
        query = dbclass.search().order_by(dbclass.title)
        results = query[get_page_startitem(page): get_page_enditem(page)]
    pagination = Pagination(query, page, PER_PAGE, query.count(), results)
    return render_template(CATEGORIES_BROWSETEMPLATES[category],
                            results=results, pagination=pagination,
                            category=category)


@kinowebapp.route('/search/', methods=['POST'])
@kinowebapp.route('/search/<searchstr>')
@kinowebapp.route('/search/<category>/<searchstr>')
@kinowebapp.route('/search/<category>/<searchstr>/<int:page>')
def search(searchstr=None, category='files', field='name', page=1):
    if category not in CATEGORIES_CLASSES:
        #TODO: Display error message to user
        return ""

    dbclass = CATEGORIES_CLASSES[category]
    searchstr = '%' + searchstr.lower().replace(' ', '%') + '%'
    if field not in dir(dbclass) or field.startswith('_'):
        # Filter out invalid and private fields
        #TODO: Display error message to user
        return ""
    if not searchstr:
        return render_template('avdanced_search.html')
    query = dbclass.query.filter(dbclass.__dict__[field].like(searchstr))
    results = (query.order_by(dbclass.id)
                  [get_page_startitem(page): get_page_enditem(page)])
    pagination = Pagination(query, page, PER_PAGE, query.count(), results)
    return render_template(CATEGORIES_BROWSETEMPLATES[category],
                           results=results, page=page, pagination=pagination,
                           category=category)


@kinowebapp.route('/details/<category>/<int:id>')
def details(category=None, id=None):
    """Displays details for any given item in a recognized category"""
    if not category or not id:
        #TODO: Display error message
        return ""
    if category not in CATEGORIES_CLASSES:
        return ""
    dbobj = CATEGORIES_CLASSES[category].get(id)
    return render_template(CATEGORIES_DETAILSTEMPLATES[category], dbobj=dbobj,
                           category=category)


@kinowebapp.route('/edit/<category>/<int:id>')
def edit(category=None, id=None):
    """Displays a mask to edit the details of a given item"""
    #TODO: Write me!
    return render_template('edit.html', category=category, id=id)
