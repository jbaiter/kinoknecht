from setuptools import setup

version = "0.1"
setup(name='kinoknecht',
      version=version,
      description=("A media management server with the ability to locally ",
                   "play back files via mplayer, an RPC-API to allow the ",
                   "implementation of MPD-like clients and a Flask-backed",
                   "webinterface for ease of administration"),
      classifiers=[
          "Programming Language :: Python",
        ],
      author="Johannes Baiter",
      author_email="johannes.baiter@gmail.com",
      license="MIT",
      packages=['kinoknecht'],
      package_data = {'kinoknecht': ['tests/test.avi']},
      scripts = ['kinoknecht/kinoknecht'],
      install_requires=[
          'Flask>=0.6.1',
          'SQLAlchemy>=0.6',
          'Flask-SQLAlchemy>=0.11',
          'IMDbPy>=4.7',
          'FFVideo>=0.0.9'
      ]
)
