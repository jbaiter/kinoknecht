# -* coding: utf8 -*-

from pprint import pprint

from simpleapi import DummyClient, Route

from test_model import create_dummy_env, remove_dummy_env
from kinoknecht.database import init_db, shutdown_db
from kinoknecht.api import DBApi

client = DummyClient(Route(DBApi, framework='dummy'))

class TestApi(object):
    def setUp(self):
        create_dummy_env()
        init_db()
        assert client.update_database()


    def tearDown(self):
        remove_dummy_env()
        shutdown_db()

    def testCreateMovie(self):
        objid = client.create(category='movie', vfiles=[1,2], imdbid=85959)
        assert objid == 0

    def testCreateShow(self):
        objid = client.create('show')
        assert objid == 0

    def testQuery(self):
        results = client.query('file', 'spam')
        pprint(results)
        assert results

    def testImdbQuery(self):
        results = client.query_imdb(searchstr='meaning of life')
        pprint(results)
        assert results

    def testGetCleanName(self):
        dirty_clean = {'The.Matrix.1998.DVDRip.XviD-KG.avi': 'The Matrix',
                u'Jean Luc Godard - Bande à part (1956).avi': u'Bande à part',
                '1938 - Opfergang.avi': 'Opfergang',
                'Diary of a Shinjuku Thief (Oshima 1974).avi': 'Diary of a Shinjuku Thief'
                }
        for title in dirty_clean:
            supposedly_clean = client.get_clean_name(fname=title)
            if dirty_clean[title] == supposedly_clean:
                continue
            else:
                print "Failed name: %s" % title
                print "Supposedly cleaned up name: %s" % supposedly_clean
                assert False


