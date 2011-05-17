from __future__ import absolute_import

import json
import os

import imdb
from sqlalchemy import and_, desc
from flask import Flask, render_template, request

import config
from kinoknecht.database import db_session
from kinoknecht.models import Videofile, Movie, Episode, Show
from kinoknecht.player import Player


kinowebapp = Flask(__name__)

CATEGORIES = {'file': Videofile, 'movie': Movie, 'episode': Episode,
              'show': Show}
i = imdb.IMDb()
mplayer = Player(config.extra_args)

def nested_jsonify(args):
    """Helper function to create a nested json response"""
    return kinowebapp.response_class(json.dumps(args, indent=None
        if request.is_xhr else 2), mimetype='application/json')

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
    if category == 'unassigned':
        vflist = Videofile.query.filter(and_(Videofile.episode == None,
                                              Videofile.movie == None))
        vflist = (vflist.order_by(desc(Videofile.creation_date))
                [page*50-50: page*50])
        return render_template('browse_files.html', objlist=vflist, page=page,
                               category=category)
    elif category not in CATEGORIES:
        return ""
    elif category == 'file':
        vflist = (Videofile.search().order_by(Videofile.name)
                  [page * 50 - 50: page * 50])
        return render_template('browse_files.html', objlist=vflist, page=page,
                               category=category)
    else:
        objlist = (CATEGORIES[category].search().order_by(
                   CATEGORIES[category].title)[page * 50 - 50: page * 50])
        return render_template('browse_meta.html', objlist=objlist, page=page,
                               category=category)


@kinowebapp.route('/search', methods=['GET', 'POST'])
def search(searchstr, category='files', field='name', page=1):
    if category not in CATEGORIES:
        #TODO: Display error message to user
        return ""
    dbclass = CATEGORIES[category]
    searchstr = '%' + searchstr + '%'
    if field not in dir(dbclass) or field.startswith('_'):
        # Filter out invalid and private fields
        #TODO: Display error message to user
        return ""
    if not searchstr:
        return render_template('avdanced_search.html')
    results = dbclass.query.filter(dbclass.__dict__[field].like(searchstr))
    results = results.order_by(dbclass.id)[page*50-50: page*50]
    return render_template('browse_files.html', objlist=results, page=page,
                           category=category)


@kinowebapp.route('/details/<category>/<int:id>')
def details(category=None, id=None):
    """Displays details for any given item in a recognized category"""
    if not category or not id:
        #TODO: Display error message
        return ""
    if category not in CATEGORIES:
        return ""
    obj = CATEGORIES[category].get(id)
    if category == 'file':
        return render_template('details_file.html', obj=obj, type='file')
    else:
        return render_template('details_meta.html', obj=obj, type=category)


@kinowebapp.route('/edit/<category>/<int:id>')
def edit(category=None, id=None):
    """Displays a mask to edit the details of a given item"""
    #TODO: Write me!
    return render_template('edit.html', category=category, id=id)


@kinowebapp.route('/play/')
@kinowebapp.route('/play/<category>/<int:id>')
def play(category=None, id=None):
    """Locally plays back a given item from a recognized category"""
    if category not in CATEGORIES or not id:
        return ""
    if category == 'file':
        vfile = Videofile.get(id)
        mplayer.loadfile(os.path.join(vfile.path, vfile.name))
        return "Success!"


@kinowebapp.route('/_query_imdb')
def _query_imdb():
    searchstr = request.args.get('searchstr', None)
    print searchstr
    results = [dict(imdbid=entry.movieID,
        title=entry['long imdb canonical title'])
        for entry in i.search_movie(searchstr)]
    return nested_jsonify(results[0:9])

@kinowebapp.route('/_create', methods=['POST'])
def _create():
    m_type = request.form['type']
    if 'vfiles[]' in request.form:
        vfiles = [Videofile.get(int(x)) for x in
                  request.form.getlist('vfiles[]')]
    if 'imdbid' in request.form:
        imdbid = request.form['imdbid']
    if 'title' in request.form:
        title = request.form['title']

    if m_type == 'movie':
        mov = Movie(videofiles=vfiles)
        try: mov.imdb_id = int(imdbid)
        except NameError: pass
        db_session.add(mov)
        db_session.commit()
        return str(mov.id)
    elif m_type == 'show':
        show = Show()
        try: show.title = title
        except NameError: pass
        db_session.add(show)
        db_session.commit()
        return str(show.id)
    elif m_type == 'episode':
        episode = Episode(vfiles[0])
        db_session.add(episode)
        db_session.commit()
        return str(episode.id)

@kinowebapp.route('/_query')
def _query():
    """Simple query for objects by name"""
    m_type = request.args.get('type')
    searchstr = request.args.get('searchstr')
    objtype = CATEGORIES[m_type]
    results = [dict(id=entry.id, title=entry.title) for entry in
            objtype.query.filter(objtype.title.like('%' + searchstr + '%'))]
    return nested_jsonify(results)

@kinowebapp.route('/_add_to_show', methods=['POST'])
def _add_to_show():
    """Adds one or more episodes to a show"""
    showid = int(request.form['showid'])
    episodes = [Episode.get(int(x))
                for x in request.form.getlist('episodeids[]')]
    show = Show.get(showid)
    for epi in episodes:
        show.episodes.append(epi)
    return str(showid)
