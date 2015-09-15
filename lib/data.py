        
import random
import string
import hashlib
from string import letters

from google.appengine.ext import db
from google.appengine.api import memcache
 
##### user stuff
def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)

def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)

def users_key(group = 'default'):
    return db.Key.from_path('users', group)
            
class User(db.Model):
    name = db.StringProperty(required = True)
    pw_hash = db.StringProperty(required = True)
    email = db.StringProperty()

    @classmethod
    def by_id(cls, uid):
        return cls.get_by_id(uid, parent = users_key())

    @classmethod
    def by_name(cls, name):
        u = cls.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, pw, email = None):
        pw_hash = make_pw_hash(name, pw)
        return cls(parent = users_key(),
                    name = name,
                    pw_hash = pw_hash,
                    email = email)

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u


            
class Page(db.Model):
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    lastModified = db.DateTimeProperty(auto_now = True)
    pathPage = db.StringProperty(required = False)
   
    @staticmethod
    def parent_key(path):
        return db.Key.from_path('pages', path)
        
    @classmethod
    def by_path(cls, path):
        q = cls.all()
        q.ancestor(cls.parent_key(path))
        q.order("-created")
        return q
    
    @classmethod
    def by_id(cls, page_id, path):
        return cls.get_by_id(page_id, cls.parent_key(path))
                   
 

class Comment(db.Model):
    content = db.TextProperty(required = True)
    author = db.ReferenceProperty(User, required = False)
    pathPage = db.StringProperty(Page, required = False)
    created = db.DateTimeProperty(auto_now_add = True)
    lastModified = db.DateTimeProperty(auto_now = True)
    upVotes = db.IntegerProperty(default=0, required = False)
    downVotes = db.IntegerProperty(default=0, required = False)
    comment_level =  db.IntegerProperty(default=1, required = False)
   
    @staticmethod
    def parent_key(path):
        return db.Key.from_path('comments', path)
                
    @classmethod
    def by_path(cls, path):
        q = cls.all()
        q.ancestor(cls.parent_key(path))
        q.order("created")
        return q
    
    @classmethod
    def by_id(cls, page_id, path):
        return cls.get_by_id(page_id, cls.parent_key(path))      



class SubComment(db.Model):
    content = db.TextProperty(required = True)
    parent_comment = db.ReferenceProperty(Comment, required = False)
    author = db.ReferenceProperty(User, required = False)
    pathPage = db.StringProperty(Page, required = False)
    created = db.DateTimeProperty(auto_now_add = True)
    lastModified = db.DateTimeProperty(auto_now = True)
    upVotes = db.IntegerProperty(default=0, required = False)
    downVotes = db.IntegerProperty(default=0, required = False)
    comment_level =  db.IntegerProperty(default=2, required = False)
   
    @staticmethod
    def parent_key(path):
        return db.Key.from_path('comments', path)
        
    @staticmethod
    def parent_comment_key(path, c_id):
        return db.Key.from_path('comments', path, 'comments', c_id)
        
    @classmethod
    def by_path(cls, path):
        q = cls.all()
        q.ancestor(cls.parent_key(path))
        q.order("created")
        return q
    
    @classmethod
    def by_path_comment(cls, path, c_id):
        q = cls.all()
        q.ancestor(cls.parent_comment_key(path, c_id))
        q.order("created")
        return q
        
    @classmethod
    def by_id(cls, page_id, path):
        return cls.get_by_id(page_id, cls.parent_key(path))        



class Conversation(db.Model):

    pathPage = db.StringProperty(required = False)
    user1 = db.StringProperty(required = True)    
    user2 = db.StringProperty(required = True)    
    
    @staticmethod
    def parent_key(path):
        return db.Key.from_path('conversation', path)
        
    @staticmethod
    def parent_conversation_key(path, c_id):
        return db.Key.from_path('conversation', path, 'conversation', c_id)
            
    @classmethod
    def by_path_conversation(cls, path, c_id):
        q = cls.all()
        q.ancestor(cls.parent_comment_key(path, c_id))
        q.order("created")
        return q
        
    @classmethod
    def by_id(cls, page_id, path):
        return cls.get_by_id(page_id, cls.parent_key(path))        



class Dialogue(db.Model):

    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    lastModified = db.DateTimeProperty(auto_now = True)
    author = db.ReferenceProperty(User, required = True)
    conversation = db.ReferenceProperty(Conversation, required = True)
    
   
    @staticmethod
    def parent_dialogue_key(path, c_id):
        return db.Key.from_path('conversation', path, 'conversation', c_id)
            
    @classmethod
    def by_path_dialogue(cls, path, c_id):
        q = cls.all()
        q.ancestor(cls.parent_dialogue_key(path, c_id))
        q.order("created")
        return q
        
    @classmethod
    def by_id(cls, page_id, path):
        return cls.get_by_id(page_id, cls.parent_key(path))      











        