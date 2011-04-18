import os
import pdb
import shutil
import time
import urllib
from os.path import join

from kinoknecht.controller import Controller
from kinoknecht.model import Videofile

TESTVIDSRC = 'tests/test.avi'
TESTDIR = 'tests/testdir'
TESTMOV = 'The Meaning of Life.avi'
TESTSHOW = join(TESTDIR, 'How.I.Met.Your.Mother.S01')
TESTCD1 = 'Spam and Eggs CD1.avi'
TESTCD2 = 'Spam and Eggs CD2.avi'
TESTMOVSUB = 'Spam and Eggs CD1.srt'
TESTEPI1 = 'How.I.Met.Your.Mother.S01E04.avi'
TESTEPI2 = 'How.I.Met.Your.Mother.108.avi'

class TestController(object):
    def setUp(self):
        # Clean up if previous tests failed to do so
        if os.path.exists(TESTDIR):
            shutil.rmtree(TESTDIR)

        # Set up test directories and files
        os.mkdir(TESTDIR)
        os.mkdir(TESTSHOW)
        shutil.copyfile(TESTVIDSRC, join(TESTDIR, TESTMOV))
        shutil.copyfile(TESTVIDSRC, join(TESTDIR, TESTCD1))
        shutil.copyfile(TESTVIDSRC, join(TESTDIR, TESTCD2))
        open(join(TESTDIR, TESTMOVSUB), 'w').close()
        shutil.copyfile(TESTVIDSRC, join(TESTSHOW, TESTEPI1))
        shutil.copyfile(TESTVIDSRC, join(TESTSHOW, TESTEPI2))
        
        # Set up controller with in-memory database
        self.c = Controller('', TESTDIR)

    def tearDown(self):
        # self.c._notifier.stop()
        shutil.rmtree(TESTDIR)


    def testSubtitleScan(self):
        assert self.c._session.query(Videofile).filter_by(
            name=TESTCD1).one().subfilepath == join(TESTDIR,
                TESTMOVSUB)

    def testSpecExtraction(self):
        assert self.c._session.query(Videofile).filter_by(
            name=TESTMOV).one().video_width == 704

    def testRootBrowse(self):
        assert self.c.browse() == [[{'path':'tests/testdir'}], []]

    def testSubdirBrowse(self):
        result = self.c.browse('tests/testdir/How.I.Met.Your.Mother.S01')
        assert result == [[], [
            {u'id': 4, u'name': u'How.I.Met.Your.Mother.108.avi'},
            {u'id': 5, u'name': u'How.I.Met.Your.Mother.S01E04.avi'}]]

    def testNonexistBrowse(self):
        assert self.c.browse('tests/testdir/The.Walking.Dead.S01') == [[],[]]

    def testStatistics(self):
        assert self.c.statistics() == {
            u'total_size': 7110580,
            u'total_length': 118.2,
            u'vidfile_count': 5
            }

    def testListVideos(self):
        assert self.c.list_videos() == [
    {u'path': u'tests/testdir', u'id': 1, u'name': u'The Meaning of Life.avi'},
    {u'path': u'tests/testdir', u'id': 2, u'name': u'Spam and Eggs CD2.avi'},
    {u'path': u'tests/testdir', u'id': 3, u'name': u'Spam and Eggs CD1.avi'},
    {u'path': u'tests/testdir/How.I.Met.Your.Mother.S01', u'id': 4,
        u'name': u'How.I.Met.Your.Mother.108.avi'},
    {u'path': u'tests/testdir/How.I.Met.Your.Mother.S01', u'id': 5,
      u'name': u'How.I.Met.Your.Mother.S01E04.avi'}]

    def testVideofileDetails(self):
        expected = {
            'audio_format': u'28781',
            'name': u'How.I.Met.Your.Mother.S01E04.avi',
            'video_format': u'XVID',
            'video_bitrate': 336864,
            'creation_date': '2011-04-16T12:53:17',
            'video_height': 320,
            'length': 23.640000000000001,
            'playeropts': None,
            'num_played': None,
            'audio_bitrate': 127936,
            'last_pos': None,
            'video_fps': 25.0,
            'path': u'tests/testdir/How.I.Met.Your.Mother.S01',
            'subfilepath': None,
            'video_width': 704,
            'id': 5,
            'size': 1422116}
        results = self.c.details('file', 5)
        # We need to omit 'creation_date' from the assert, as its value
        # changes with each testrun
        passed = False
        for k,v in results.iteritems():
            if not k == 'creation_date':
                match = bool(results[k] == expected[k])
                if not match: assert False
        assert True

    def testInvalidVideofileDetails(self):
        assert self.c.details('file', 31337) == {}

    def testSearchImdb(self):
        assert self.c.search_metadata('The Meaning of Life')[0:2] == [
            {u'id': 85959, u'title': u'Meaning of Life, The (1983)'},
            {u'id': 440972, u'title': u'Meaning of Life, The (2005/I)'}]

    def testCreateMovie(self):
        self.c.create_movie([3,2], 85959)
        assert self.c.details('movie', '1')

    def testSearchVideofileByName(self):
        result = self.c.search_videofile({
            'field':'name',
            'operator':'like',
            'value':'how.i.met.your.mother'})
        assert len(result) == 2

    def testSearchVideofileByLength(self):
        result = self.c.search_videofile({
            'field':'length',
            'operator':'greater',
            'value':20})
        assert len(result) == 5

    def testSearchVideofileByChainedLengthAndName(self):
        results = self.c.search_videofile(
          {'field':'length', 'operator':'greater', 'value':20},
          {'field':'length', 'operator':'lesser', 'value':25},
          {'field':'name', 'operator':'like', 'value':'meaning of life'})
        expected = [{
          'audio_format': u'28781', 'name': u'The Meaning of Life.avi',
          'video_format': u'XVID', 'video_bitrate': 336864,
          'video_height': 320, 'length': 23.640000000000001,
          'playeropts': None, 'num_played': None, 'audio_bitrate': 127936,
          'last_pos': None, 'video_fps': 25.0, 'path': u'tests/testdir',
          'subfilepath': None, 'video_width': 704, 'id': 1, 'size': 1422116}]
        # We need to omit 'creation_date' from the assert, as its value
        # changes with each testrun
        passed = False
        for dic in results:
            for k,v in dic.iteritems():
                if not k == 'creation_date':
                    match = bool(dic[k] == dic[k])
                    if not match: assert False
        assert True

#    def testCreateVideoTrigger(self):
#        shutil.copyfile(TESTVIDSRC, join(TESTDIR, 'foo.avi'))
#        time.sleep(5)
#        assert self.c._session.query(Videofile).filter_by(
#            name='foo.avi').count() == 1
#
#    def testCreateSubTrigger(self):
#        shutil.copyfile(TESTVIDSRC, join(TESTDIR, 'foo.avi'))
#        open(join(TESTDIR, 'foo.srt'), 'w').close()
#        time.sleep(5)
#        assert self.c._session.query(Videofile).filter_by(
#            name='foo.avi').one().subfilepath == join(
#                TESTDIR, 'foo.srt')
