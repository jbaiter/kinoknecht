kinoknecht
==========
Another movie-database among myriads of others.

This one is built upon Flask/SQLAlchemy and supports local playback of
videofiles. Its main purpose is to act as a kind of 'mpd' for moving pictures
for people like me, who have their TV/projector hooked up to an otherwise
headless machine and would like to control it from another machine.

Be aware that is not really in a usable state at the moment, you can scan your
media directories and browse the collection in your browser, but the JSONRPC-
API doesn't work yet, metadata support is still very preliminary and control
of the playback instance is not implemented yet.

This is very much a research project for me, so please comment on bad code,
bad design, bad documentation, bad testcases, anything really, I'm eager to
learn :-)
