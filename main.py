import os
import re
import random
import hashlib
import hmac
import logging
import json
import sys

from string import letters
from datetime import datetime, timedelta

from lib import utils, data
from lib.data import Page, Comment

import webapp2
import jinja2


from google.appengine.ext import db
from google.appengine.api import memcache

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)


class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        params['gray_style'] = utils.gray_style
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def render_json(self, d):
        json_txt = json.dumps(d)
        self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
        self.write(json_txt)

    def set_secure_cookie(self, name, val):
        cookie_val = utils.make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and utils.check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and data.User.by_id(int(uid))
        #self.can_post = self.user and self.user.name == 'spez'

        if self.request.url.endswith('.json'):
            self.format = 'json'
        else:
            self.format = 'html'
    
    def notfound(self):
        self.error(404)
        self.write('<h1>404: Not Found</h1>Sorry, my friend but the page does not exist.')



class Signup(Handler):
    def get(self):
        next_url = self.request.headers.get('referer', '/')
        self.render("signup-form.html", next_url = next_url)

    def post(self):
        have_error = False
        
        next_url = str(self.request.get('next_url'))
        if not next_url or next_url.startswith('/login'):
            next_url = '/'
        
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')

        params = dict(username = self.username,
                      email = self.email)

        if not utils.valid_username(self.username):
            params['error_username'] = "That's not a valid username."
            have_error = True

        if not utils.valid_password(self.password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True

        if not utils.valid_email(self.email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('signup-form.html', **params)
        else:           
            #make sure the user doesn't already exist
            u = data.User.by_name(self.username)
            if u:
                msg = 'That user already exists.'
                self.render('signup-form.html', error_username = msg)
            else:
                u = data.User.register(self.username, self.password, self.email)
                u.put()

                self.login(u)
                self.redirect(next_url)

class Login(Handler):
    def get(self):
        next_url = self.request.headers.get('referer', '/')
        self.render('login-form.html', next_url = next_url)

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        
        next_url = str(self.request.get('next_url'))
        if not next_url or next_url.startswith('/login'):
            next_url = '/'
        
        u = data.User.login(username, password)
        if u:
            self.login(u)
            self.redirect(next_url)
        else:
            msg = 'Invalid login'
            self.render('login-form.html', error = msg)

class Logout(Handler):
    def get(self):
        next_url = self.request.headers.get('referer', '/')
        self.logout()
        self.redirect(next_url)



class EditPage(Handler):
    def get(self, path):
        if not self.user:
            self.redirect('/login')
        
        v = self.request.get('v')
        p = None
        if v:
            if v.isdigit():
                p = data.Page.by_id(int(v), path)
                
            if not p:
                return self.notfound()
                
        else:
            p = data.Page.by_path(path).get() 
            
        logging.error("EditPageGet"+str(path))
            
        self.render("edit.html", path = path, page = p)

    def post(self, path):
        if not self.user:
            self.error(400)
            return
            
        content = self.request.get('content')
        old_page = data.Page.by_path(path).get()
        
        #what to do when empty content is submitted?
        if not (old_page or content):
            return
        elif not old_page or old_page.content != content:
            p = data.Page(parent = data.Page.parent_key(path), content = content, pathPage = path)
            p.put()
            
        self.redirect(path)
        
class HistoryPage(Handler):
    def get(self, path):
        q = data.Page.by_path(path)
        q.fetch(limit = 100)
        
        posts = list(q)
        if posts:
            self.render("history.html", path = path, posts = posts)
        else:
            self.redirect("/_edit" + path)
                
        
class UserPage(Handler):
    def get(self, path):
        
        path = "/user" + path
        v = self.request.get('v')
        p = None
        if v:
            if v.isdigit():
                p = data.Page.by_id(int(v), path)
                
            if not p:
                return self.notfound()
                
        else:
            p = data.Page.by_path(path).get()
        
        logging.error("UserPageGet"+str(path))
        
        comment_page = data.Comment.by_path(path)  
        comment_page = list(comment_page)          
        
        temp_list = []
        
        for c in comment_page:
            temp_list.append(c)            
            d = data.SubComment.by_path_comment(path, int(c.key().id()))
            if d:
                for temp in d:
                    temp_list.append(temp)
            
        comment_page = temp_list
    
        comment_recent = data.Comment.all().order('-created').fetch(10)            
        comment_recent = list(comment_recent)   
        pages = data.Page.all().order('pathPage')
        
        if p:
            self.render("user-form.html", page = p, path = path, comment_page = comment_page, comment_recent = comment_recent, pages = pages)
        else:
            self.redirect("/_edit" + path)

    def post(self, path):
        if not self.user:
            return self.redirect("/login")
        
        path = "/user" + path
        content = self.request.get('content')        
        old_page = data.Page.by_path(path).get()
        
        #what to do when empty content is submitted?
        if not (old_page or content):
            logging.error("Merde")
            return
        elif not old_page or old_page.content != content:
            c = data.Comment(parent = data.Comment.parent_key(path), content = content, author = self.user, pathPage = path)
            c.put()
            
        p = data.Page.by_path(path).get() #get gets the first element of the query
                
        comment_page = data.Comment.by_path(path)  
        comment_page = list(comment_page)          
        
        temp_list = []
        
        for c in comment_page:
            temp_list.append(c)            
            d = data.SubComment.by_path_comment(path, int(c.key().id()))
            if d:
                for temp in d:
                    temp_list.append(temp)
            
        comment_page = temp_list
    
        comment_recent = data.Comment.all().order('-created').fetch(10)            
        comment_recent = list(comment_recent)   
        pages = data.Page.all().order('pathPage')
        
        self.render("user-form.html", page = p, path = path, comment_page = comment_page, comment_recent = comment_recent, pages = pages)

        
class WikiPage(Handler):
    def get(self, path):
        
        v = self.request.get('v')
        p = None
        if v:
            if v.isdigit():
                p = data.Page.by_id(int(v), path)
                
            if not p:
                return self.notfound()
                
        else:
            p = data.Page.by_path(path).get()
        
        logging.error("WikiPageGet"+str(path))
        
        comment_page = data.Comment.by_path(path)  
        comment_page = list(comment_page)          
        
        temp_list = []
        
        for c in comment_page:
            temp_list.append(c)            
            d = data.SubComment.by_path_comment(path, int(c.key().id()))
            if d:
                for temp in d:
                    temp_list.append(temp)
            
        comment_page = temp_list
    
        comment_recent = data.Comment.all().order('-created').fetch(10)            
        comment_recent = list(comment_recent)   
        pages = data.Page.all().order('pathPage')
        
        if p:
            self.render("page.html", page = p, path = path, comment_page = comment_page, comment_recent = comment_recent, pages = pages)
        else:
            self.redirect("/_edit" + path)

    def post(self, path):
        if not self.user:
            return self.redirect("/login")
            
        content = self.request.get('content')        
        old_page = data.Page.by_path(path).get()
        
        #what to do when empty content is submitted?
        if not (old_page or content):
            logging.error("Merde")
            return
        elif not old_page or old_page.content != content:
            c = data.Comment(parent = data.Comment.parent_key(path), content = content, author = self.user, pathPage = path)
            c.put()
            
        p = data.Page.by_path(path).get() #get gets the first element of the query
                
        comment_page = data.Comment.by_path(path)  
        comment_page = list(comment_page)          
        
        temp_list = []
        
        for c in comment_page:
            temp_list.append(c)            
            d = data.SubComment.by_path_comment(path, int(c.key().id()))
            if d:
                for temp in d:
                    temp_list.append(temp)
            
        comment_page = temp_list
    
        comment_recent = data.Comment.all().order('-created').fetch(10)            
        comment_recent = list(comment_recent)   
        pages = data.Page.all().order('pathPage')
        
        self.render("page.html", page = p, path = path, comment_page = comment_page, comment_recent = comment_recent, pages = pages)


class CommentPage(Handler):
    def get(self, path):
        
        id = self.request.get('id')
        
        p = None
        if id:
            if id.isdigit():
                p = data.Comment.by_id(int(id), path)
                
            if not p:
                return self.notfound()           
        
        #Get the comments
         
        logging.error("CommentPageGet"+str(path))
        
        pages = data.Page.all().order('pathPage')
        
        sub_comments = data.SubComment.by_path_comment(path, int(id))
        sub_comments = list(sub_comments)
        
        if p:
            self.render("comment-form.html", path = path, c = p, pages = pages, sub_comments = sub_comments)
        else:
            self.redirect("/_edit" + path)

    def post(self, path):
        if not self.user:
            self.error(400)
            return
            
        content = self.request.get('content')        
        
        id = self.request.get('id')
        
        p = None
        if id:
            if id.isdigit():
                p = data.Comment.by_id(int(id), path)
                
            if not p:
                return self.notfound()
                
        old_page = data.Page.by_path(path).get()
        
        #what to do when empty content is submitted?
        if not (old_page or content):
            logging.error("Merde")
            return
        elif not old_page or old_page.content != content:
            c = data.SubComment(parent = data.SubComment.parent_comment_key(path, int(id)), content = content, author = self.user, pathPage = path)
            c.put()
            
        #Get the comments
                        
        pages = data.Page.all().order('pathPage')
        
        sub_comments = data.SubComment.by_path_comment(path, int(id))
        sub_comments = list(sub_comments)
        
        if p:
            self.render("comment-form.html", path = path, c = p, pages = pages, sub_comments = sub_comments)
        else:
            self.redirect("/_edit" + path)


class ConversationPage(Handler):
    def get(self, path):
        
        id = self.request.get('id')
        
        if id:
            
            logging.error("ConversationPageGetId"+str(path))
            logging.error(str(id))
            
            comment_page = data.Dialogue.by_path_dialogue(path, int(id))  
            comment_page = list(comment_page)          
                
            comment_recent = data.Comment.all().order('-created').fetch(10)            
            comment_recent = list(comment_recent)   
            pages = data.Page.all().order('pathPage')
            
            self.render("conversation-form.html", path = path, comment_page = comment_page, comment_recent = comment_recent, pages = pages)
        else:
            u = self.request.get('u')
            v = self.request.get('v')
            
            logging.error("ConversationPageGetUV"+str(path))
            logging.error(str(u))
            logging.error(str(v))
            
            user1 = sorted([u,v])[0]
            user2 = sorted([u,v])[1]
            logging.error(str(user1))
            logging.error(str(user2))
            
            c = data.Conversation(user1 = user1, user2 = user2, pathPage = path)
            id = c.key().id()
            c.put()
            
            self.redirect("/conversation/?id=" + id)
        

    def post(self, path):
        if not self.user:
            return self.redirect("/login")
            
        content = self.request.get('content')  
        u = self.request.get('u')
        v = self.request.get('v')   
        user1 = sorted([u,v])[0]
        user2 = sorted([u,v])[1]        
        
        #what to do when empty content is submitted?
        if content:
            c = data.Conversation(parent = data.Conversation.parent_conversation_key(path, user1, user2), content = content, author = self.user, user1 = user1, user2 = user2, pathPage = path)
            c.put()
            
        comment_page = data.Conversation.by_path_conversation(path, user1, user2)  
        comment_page = list(comment_page)          
            
        comment_recent = data.Comment.all().order('-created').fetch(10)            
        comment_recent = list(comment_recent)   
        pages = data.Page.all().order('pathPage')
        
        self.render("conversation-form.html", path = path, comment_page = comment_page, comment_recent = comment_recent, pages = pages)

         

PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'
         
app = webapp2.WSGIApplication([('/signup', Signup),
                               ('/login', Login),
                               ('/logout', Logout),
                               ('/user' + PAGE_RE, UserPage),
                               ('/comment' + PAGE_RE, CommentPage),
                               ('/conversation' + PAGE_RE, ConversationPage),
                               ('/_history' + PAGE_RE, HistoryPage),
                               ('/_edit' + PAGE_RE, EditPage),
                               (PAGE_RE, WikiPage),
                               ],
                              debug=True)
