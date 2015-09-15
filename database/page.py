from google.appengine.ext import db
from google.appengine.api import memcache

class Page(db.Model):
    content = db.TextProperty(required = True)
    #author = db.ReferenceProperty(User, required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)
   
    @staticmethod
    def parent_key(path):
        return db.Key.from_path('/root' + path, 'pages')
        
    @classmethod
    def by_path(cls, path):
        q = cls.all()
        q.ancestor(cls.parent_key(path))
        q.order("-created")
        return q
    
    @classmethod
    def by_id(cls, page_id, path):
        return cls.get_by_id(page_id, cls.parent_key(path))