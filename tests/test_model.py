import os
import shutil
from os.path import join

from kinoknecht import config
config.video_dirs = ['tests/testdir']
config.log_file = 'tests/logdir/dummy.log'
config.db_file = 'tests/dummy.db'

from kinoknecht.database import init_db, shutdown_db
from kinoknecht.models import Videofile, Movie

TESTVIDSRC = 'tests/test.avi'
TESTDIR = 'tests/testdir'
TESTMOV = 'The Meaning of Life.avi'
TESTSHOW = join(TESTDIR, 'How.I.Met.Your.Mother.S01')
TESTCD1 = 'Spam and Eggs CD1.avi'
TESTCD2 = 'Spam and Eggs CD2.avi'
TESTMOVSUB = 'Spam and Eggs CD1.srt'
TESTEPI1 = 'How.I.Met.Your.Mother.S01E04.avi'
TESTEPI2 = 'How.I.Met.Your.Mother.108.avi'

def create_dummy_env():
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

def remove_dummy_env():
    shutil.rmtree(TESTDIR)


class TestModel(object):
    def setUp(self):
        create_dummy_env()
        init_db()
        Videofile.update_all()

    def tearDown(self):
        remove_dummy_env()
        shutdown_db()

    def testSubtitleScan(self):
        assert (Videofile.search(Videofile.name == TESTCD1).one().subfilepath
                == os.path.abspath(join(TESTDIR, TESTMOVSUB)))

    def testSpecExtraction(self):
        assert (Videofile.search(Videofile.name == TESTMOV).one()
                .video_width == 704)

    def testRootBrowse(self):
        assert Videofile.browse() == [['tests/testdir'], []]

    def testSubdirBrowse(self):
        result = Videofile.browse(
                os.path.abspath('tests/testdir/How.I.Met.Your.Mother.S01'))
        assert (
            result[1][0].name == u'How.I.Met.Your.Mother.108.avi' and
            result[1][1].name == u'How.I.Met.Your.Mother.S01E04.avi'
        )

    def testNonexistBrowse(self):
        assert Videofile.browse(
            'tests/testdir/The.Walking.Dead.S01') == [[], []]

    def testVideofileStatistics(self):
        assert Videofile.statistics() == {
            u'total_size': 7110580,
            u'total_length': 118.2,
            u'vidfile_count': 5
        }

    def testListVideos(self):
        result = Videofile.search()
        assert (
            result[0].name == u'The Meaning of Life.avi' and
            result[1].name == u'Spam and Eggs CD2.avi' and
            result[2].name == u'Spam and Eggs CD1.avi' and
            result[3].name == u'How.I.Met.Your.Mother.108.avi' and
            result[4].name == u'How.I.Met.Your.Mother.S01E04.avi'
        )

    def testVideofileInfodict(self):
        expected = {
            'audio_bitrate': None, 'audio_format': None,
            'id': 5, 'last_pos': None, 'length': 23.640000000000001,
            'name': u'How.I.Met.Your.Mother.S01E04.avi', 'num_played': None,
            'path': os.path.abspath('tests/testdir/How.I.Met.Your.Mother.S01'),
            'playeropts': None, 'size': 1422116, 'subfilepath': None,
            'video_bitrate': None, 'video_format': u'mpeg4', 'video_fps': 25.0,
            'video_height': 320, 'video_width': 704,
            'title': u'How.I.Met.Your.Mother.S01E04.avi',
            'sha1hash': u'de4167ee4347fda2796e2d5fe99183828e41bf61'
        }
        results = Videofile.get(5).get_infodict()
        # We need to omit 'creation_date' from the assert, as its value
        # changes with each testrun
        for k, v in results.iteritems():
            if not k == 'creation_date':
                match = bool(results[k] == expected[k])
                if not match:
                    assert False
        assert True

    def testGetInvalidVideofile(self):
        assert bool(Videofile.get(12)) == False

    def testCreateMovie(self):
        mov = Movie(videofiles=[Videofile.get(3), Videofile.get(2)],
                    imdb_id=85959)
        assert len(mov.videofiles) == 2 and mov.year == 1983

    def testSearchVideofileByName(self):
        result = Videofile.search(
            Videofile.name.like('%how.i.met.your.mother%')
        )
        assert result.count() == 2

    def testSearchVideofileByLength(self):
        result = Videofile.search(Videofile.length > 20)
        assert result.count() == 5

    def testSearchVideofileByLengthAndName(self):
        result = Videofile.search(
            Videofile.length > 20,
            Videofile.length < 25,
            Videofile.name.like('%meaning of life%')
        ).one().get_infodict()
        expected = {
                'audio_bitrate': None, 'audio_format': None,
                'id': 1, 'last_pos': None, 'length': 23.640000000000001,
                'name': u'The Meaning of Life.avi', 'num_played': None,
                'path': unicode(os.path.abspath('tests/testdir')),
                'playeropts': None, 'size': 1422116, 'subfilepath': None,
                'video_bitrate': None, 'video_format': u'mpeg4',
                'sha1hash': u'de4167ee4347fda2796e2d5fe99183828e41bf61',
                'video_fps': 25.0, 'video_height': 320, 'video_width': 704
        }
        # We need to omit 'creation_date' from the assert, as its value
        # changes with each testrun
        for k, v in result.iteritems():
            if not k == 'creation_date':
                match = bool(result[k] == expected[k])
                if not match:
                    assert False
        assert True

    def testUpdateVideofiles(self):
        Videofile.update_all()
        assert Videofile.search().count() == 5
