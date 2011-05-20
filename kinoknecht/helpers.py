import json

CATEGORIES = {'file': Videofile, 'movie': Movie, 'episode': Episode,
              'show': Show, 'unassigned': Videofile}

def to_unicode(string):
    """ Force unicode on string"""
    #TODO: This smells, there must be a more proper way to do this
    if not isinstance(string, unicode):
        try:
            return unicode(string)
        except UnicodeDecodeError:
            return unicode(string, errors='replace')
    else:
        return string

def imdbcontainer_to_json(key, value):
    container = None
    if key == 'akas':
        container = list(dict(
                (('country', x.split('::')[1]), ('title', x.split('::')[0]))
                             ) for x in value)
    elif key == 'runtimes':
        container = []
        for entry in value:
            singlesplit = entry.split(':')
            if len(singlesplit) == 2:
                container.append("%s (%s)" % singlesplit[1], singlesplit[0])
            else:
                container.append(entry)
    else:
        container = json.dumps(value)
    return json.dumps(container)
