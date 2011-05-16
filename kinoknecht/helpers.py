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
