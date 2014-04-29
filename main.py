# appcfg.py --no_cookies --email=jonmcire@gmail.com --passin rollback ./


__author__ = ('Thomas Dowling, '
              'thomasgdowling@gmail.com')


import cgi
import os
import time
import urllib
import wsgiref.handlers

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

import atom
import gdata.alt.appengine
import gdata.calendar.service
import gdata.contacts.service
import gdata.service

# Information about this application
APP_INFO = """This """

APP_NAME = 'Sports Friends'
CSS_LINK = '<link type="text/css" rel="stylesheet" href="/stylesheets/main.css" />'
# Change the value of HOST_NAME to the name given to point to your app.
HOST_NAME = 'zaradowfriends.appspot.com'
# Default values for new events
SAMPLE_EVENT_DESCRIPTION = ''
SAMPLE_EVENT_TITLE = ''

class PersonalDetails(db.Model):
    uname = db.UserProperty()
    firstname = db.StringProperty(multiline=True)
    surname = db.StringProperty(multiline=True)
    address1 = db.StringProperty(multiline=True)
    address2 = db.StringProperty(multiline=True)
    town = db.StringProperty(multiline=True)
    county = db.StringProperty(multiline=True)
    phone = db.StringProperty(multiline=True)
    desc = db.StringProperty(multiline=True)
    googlelink = db.StringProperty(multiline=True)
    date = db.DateTimeProperty(auto_now_add=True)
    
class StoredToken(db.Model):
  user_email = db.StringProperty(required=True)
  session_token = db.StringProperty(required=True)

class EventDetails(db.Model):
    author = db.UserProperty()
    eventname = db.StringProperty(multiline=True)
    description = db.StringProperty(multiline=True)
    date = db.StringProperty(multiline=True)
    location = db.StringProperty(multiline=True)
    location_cord1 = db.StringProperty(multiline=True)
    location_cord2 = db.StringProperty(multiline=True)

class EventAtendees(db.Model):
    atendee = db.UserProperty()
    eventid = db.StringProperty(multiline=True)
    eventname = db.StringProperty(multiline=True)
    date = db.StringProperty(multiline=True)
    location = db.StringProperty(multiline=True)

class Comments(db.Model):
    author = db.UserProperty()
    eventid = db.StringProperty(multiline=True)
    comment = db.StringProperty(multiline=True)
    date = db.DateTimeProperty(auto_now_add=True)
    
class CalendarContacts(webapp.RequestHandler):

  # Initialize some global variables we will use
  def __init__(self):
    # Stores the page's current user
    self.current_user = None
    # Stores the token_scope information
    self.token_scope = None
    # Stores the Google Data Client
    self.client = None
    # The one time use token value from the URL after the AuthSub redirect.
    self.token = None
    # Init local time - default date for new events
    localtime = time.localtime()
    self.todays_date = "%s-%s-%s" % (localtime[0], localtime[1], localtime[2])

  def post(self):
    event_status = 'not_created'
    event_link = None

    # Get the current user
    self.current_user = users.GetCurrentUser()

    # Manage our Authentication for the user
    self.ManageAuth()
    self.LookupToken()
   
    form = cgi.FieldStorage()

    attendee_list = []
    if form.has_key('event_attendees') and form['event_attendees'] is not None:
      if isinstance(form['event_attendees'], list):
        for attendee in form['event_attendees']:
          attendee_list.append(attendee.value)
      else:
        attendee_list.append(form['event_attendees'].value)

    event = self.InsertEvent(form['event_title'].value,
        form['location'].value,
        form['event_description'].value,
        form['datepicker'].value,
        attendee_list)
    if event is not None:
        alt_link = event.GetAlternateLink().href
        self_link = event.GetSelfLink().href
        xml = self.FormatXML("%s" % event.ToString())
        event_status = 'created'

    ed = EventDetails()
    if users.get_current_user():
        ed.author = users.get_current_user()
    ed.eventname = form['event_title'].value
    ed.description = form['event_description'].value
    ed.date = form['datepicker'].value
    ed.location = form['location'].value
    ed.location_cord1 = form['lat'].value
    ed.location_cord2 = form['lng'].value
    ed.put()

       
    template_values = {
      'event_status': event_status,
      'alt_link': alt_link,
      'self_link': self_link,
      'xml': xml,
      'event_title': form['event_title'],
      'event_description': form['event_description'],
      'attendee_list': attendee_list,
      'app_name': APP_NAME,
      'css_link': CSS_LINK,
      }

    self.redirect('/ViewCal')
    template_file = 'process_event.html'
    path = os.path.join(os.path.dirname(__file__), 'main_templates', 
        template_file)
    self.response.out.write(template.render(path, template_values))

  def get(self):
    # Get the current user
    self.current_user = users.GetCurrentUser()

    if not self.current_user:
      template_values = {
        'login_url': users.CreateLoginURL(self.request.uri),
        'app_name': APP_NAME,
        'css_link': CSS_LINK,
        'app_info': APP_INFO
        }
      template_file = 'login.html'
    else:
      self.token = self.request.get('token')

      # Manage our Authentication for the user
      self.ManageAuth()
      self.LookupToken()
      
      if self.client.GetAuthSubToken() is not None:
        self.response.out.write('<div id="main">')
        self.feed_url = 'http://www.google.com/calendar/feeds/default/private/full'
        contacts = self.GetContacts()
        template_values = {
          'current_user': self.current_user,
          'logout_url': users.CreateLogoutURL(self.request.uri),
          'contacts': contacts,
          'app_name': APP_NAME,
          'css_link': CSS_LINK,
          'todays_date': self.todays_date,
          'sample_event_title': SAMPLE_EVENT_TITLE,
          'sample_event_description': SAMPLE_EVENT_DESCRIPTION
          }
        template_file = 'CreateEventForm.html'
      else:
        template_values = {
          'authsub_url': self.client.GenerateAuthSubURL(
              'http://%s/' % (HOST_NAME),
              '%s %s' % ('http://www.google.com/m8/feeds/', 
                  'http://www.google.com/calendar/feeds'),
              secure=False, session=True),
              'app_name': APP_NAME,
              'css_link': CSS_LINK
          }
        template_file = 'authorize_access.html'

    path = os.path.join(os.path.dirname(__file__), 'main_templates', 
        template_file)
    self.response.out.write(template.render(path, template_values))

  def ManageAuth(self):
    self.client = gdata.service.GDataService()
    gdata.alt.appengine.run_on_appengine(self.client)
    if self.token:
      # Upgrade to a session token and store the session token.
      self.UpgradeAndStoreToken()

  def LookupToken(self):
    if self.current_user:
      stored_tokens = StoredToken.gql('WHERE user_email = :1',
          self.current_user.email())
      for token in stored_tokens:
        self.client.SetAuthSubToken(token.session_token)
        return

  def UpgradeAndStoreToken(self):
    self.client.SetAuthSubToken(self.token)
    self.client.UpgradeToSessionToken()
    if self.current_user:
      # Create a new token object for the data store which associates the
      # session token with the requested URL and the current user.
      new_token = StoredToken(user_email=self.current_user.email(), 
          session_token=self.client.GetAuthSubToken())
          
      new_token.put()
      self.redirect('http://%s/' % HOST_NAME)

  def GetContacts(self):
    self.contacts_client = gdata.contacts.service.ContactsService()
    gdata.alt.appengine.run_on_appengine(self.contacts_client)
    self.contacts_client.SetAuthSubToken(self.client.GetAuthSubToken())
    contacts_feed = self.contacts_client.GetContactsFeed()
    contacts_dict = {}
    for contact in contacts_feed.entry:
      for email in contact.email:
        if email.primary and email.primary == 'true':
          email.address
          if contact.title.text is not None:
            contacts_dict['%s - %s' % 
                (contact.title.text, email.address)] = email.address
          else:
            contacts_dict[email.address] = email.address
    return contacts_dict

  def InsertEvent(self, title, location, description=None, start_time=None, attendees=[]):
    self.calendar_client = gdata.calendar.service.CalendarService()
    gdata.alt.appengine.run_on_appengine(self.calendar_client)
    self.calendar_client.SetAuthSubToken(self.client.GetAuthSubToken())

    event = gdata.calendar.CalendarEventEntry()
    event.title = atom.Title(text=title)
    event.content = atom.Content(text=description)
    event.where.append(gdata.calendar.Where(value_string=location))
    event.when.append(gdata.calendar.When(start_time=start_time))

    for attendee in attendees:
      who = gdata.calendar.Who()
      who.email = attendee
      event.who.append(who)

    new_event = self.calendar_client.InsertEvent(event,
        '/calendar/feeds/default/private/full')

    return new_event

  def FormatXML(self, xmlstring):
    """Helper method to format XML into browser-friendly output."""
    output = xmlstring.replace('<', '&lt;')
    output = output.replace('>', '&gt;')
    output = output.replace('&gt;&lt;', '&gt;<br />&lt;')
    return output

# --------------------------------------------------------------------------
class UserAddCalendar(webapp.RequestHandler):
  def __init__(self):
    self.current_user = None
    self.token_scope = None
    self.client = None
    self.token = None
    localtime = time.localtime()
    self.todays_date = "%s-%s-%s" % (localtime[0], localtime[1], localtime[2])

  def get(self):
    eventid = self.request.get('eventid')
    event_title = self.request.get('event_title')
    event_description = self.request.get('event_description')
    datepicker = self.request.get('datepicker')
    location = self.request.get('location')
    
    event_status = 'not_created'
    event_link = None

    # Get the current user
    self.current_user = users.GetCurrentUser()

    # Manage our Authentication for the user
    self.ManageAuth()
    self.LookupToken()
   
    form = cgi.FieldStorage()

    attendee_list = []
    if form.has_key('event_attendees') and form['event_attendees'] is not None:
      if isinstance(form['event_attendees'], list):
        for attendee in form['event_attendees']:
          attendee_list.append(attendee.value)
      else:
        attendee_list.append(form['event_attendees'].value)

    event = self.InsertEvent(event_title,
        location,
        event_description,
        datepicker,
        attendee_list)
    if event is not None:
        alt_link = event.GetAlternateLink().href
        self_link = event.GetSelfLink().href
        xml = self.FormatXML("%s" % event.ToString())
        event_status = 'created'

    ea = EventAtendees()
    if users.get_current_user():
        ea.atendee = users.get_current_user()
    ea.eventid = eventid
    ea.eventname = event_title
    ea.date = datepicker
    ea.location = location
    ea.put()

    events = db.GqlQuery("SELECT * FROM PersonalDetails WHERE uname = :1", users.get_current_user())
    dlink = ""
    for event in events:
        dlink = self.response.out.write('<td>%s</td>' % event.googlelink)
    self.response.out.write(dlink)
    #self.response.out.write("<iframe src=\"https://www.google.com/calendar/embed?src=jonmcire%40gmail.com&ctz=Europe/Dublin\" style=\"border: 0\" width=\"530\" height=\"400\" frameborder=\"0\" scrolling=\"no\"></iframe>")

  def ManageAuth(self):
    self.client = gdata.service.GDataService()
    gdata.alt.appengine.run_on_appengine(self.client)
    if self.token:
      # Upgrade to a session token and store the session token.
      self.UpgradeAndStoreToken()

  def LookupToken(self):
    if self.current_user:
      stored_tokens = StoredToken.gql('WHERE user_email = :1',
          self.current_user.email())
      for token in stored_tokens:
        self.client.SetAuthSubToken(token.session_token)
        return

  def UpgradeAndStoreToken(self):
    self.client.SetAuthSubToken(self.token)
    self.client.UpgradeToSessionToken()
    if self.current_user:
      # Create a new token object for the data store which associates the
      # session token with the requested URL and the current user.
      new_token = StoredToken(user_email=self.current_user.email(), 
          session_token=self.client.GetAuthSubToken())
          
      new_token.put()
      self.redirect('http://%s/' % HOST_NAME)

  def GetContacts(self):
    self.contacts_client = gdata.contacts.service.ContactsService()
    gdata.alt.appengine.run_on_appengine(self.contacts_client)
    self.contacts_client.SetAuthSubToken(self.client.GetAuthSubToken())
    contacts_feed = self.contacts_client.GetContactsFeed()
    contacts_dict = {}
    for contact in contacts_feed.entry:
      for email in contact.email:
        if email.primary and email.primary == 'true':
          email.address
          if contact.title.text is not None:
            contacts_dict['%s - %s' % 
                (contact.title.text, email.address)] = email.address
          else:
            contacts_dict[email.address] = email.address
    return contacts_dict

  def InsertEvent(self, title, location, description=None, start_time=None, attendees=[]):
    self.calendar_client = gdata.calendar.service.CalendarService()
    gdata.alt.appengine.run_on_appengine(self.calendar_client)
    self.calendar_client.SetAuthSubToken(self.client.GetAuthSubToken())

    event = gdata.calendar.CalendarEventEntry()
    event.title = atom.Title(text=title)
    event.content = atom.Content(text=description)
    event.where.append(gdata.calendar.Where(value_string=location))
    event.when.append(gdata.calendar.When(start_time=start_time))

    for attendee in attendees:
      who = gdata.calendar.Who()
      who.email = attendee
      event.who.append(who)

    new_event = self.calendar_client.InsertEvent(event,
        '/calendar/feeds/default/private/full')

    return new_event

  def FormatXML(self, xmlstring):
    """Helper method to format XML into browser-friendly output."""
    output = xmlstring.replace('<', '&lt;')
    output = output.replace('>', '&gt;')
    output = output.replace('&gt;&lt;', '&gt;<br />&lt;')
    return output

# -----------------------------------------------------------------
class ListEvents(webapp.RequestHandler):
    def get(self):
        events = db.GqlQuery("SELECT * FROM EventDetails")
        self.response.out.write('<table border=0 class=\"eventtext\" width=100%>')
        self.response.out.write('<tr class=\"tblheader\"><th>Event</th><th>Date</th><th>Location</th><th></th></tr>')
        for event in events:
               self.response.out.write('<tr>')
               #self.response.out.write('<td>%s</td>' % event.key().id())
               #self.response.out.write('<td>%s</td>' % event.author)
               self.response.out.write('<td>%s</td>' % event.eventname)
               #self.response.out.write('<td>%s</td>' % event.description)
               self.response.out.write('<td>%s</td>' % event.date)
               self.response.out.write('<td>%s</td>' % event.location)
               #self.response.out.write('<td>%s</td>' % event.location_cord1)
               #self.response.out.write('<td>%s</td>' % event.location_cord2)
               #self.response.out.write('<td><a href=\"viewevent?eventid=%s\">View</a></td>' % event.key().id())
               self.response.out.write('<td><a href=# onclick=\"CLoad(\'Event Viewer\',\'/viewevent?eventid=%s\')\">View</a></td>' % event.key().id())
               self.response.out.write('</tr>')
        self.response.out.write('</table>')

class SearchEvents(webapp.RequestHandler):
    def get(self):
        sport = self.request.get('sport')
        location = self.request.get('location')
        events = db.GqlQuery("SELECT * FROM EventDetails")
        self.response.out.write('<table border=0 class=\"eventtext\" width=100%>')
        self.response.out.write('<tr class=\"tblheader\"><th>Event</th><th>Date</th><th>Location</th><th></th></tr>')
        counter=0
        for event in events:
             res = -1
             res1 = -1
             res2 = -1
             if len(sport) > 0:
               res = event.description.lower().find(sport.lower())
               res1 = event.eventname.lower().find(sport.lower())
             else:
               res = -1
               res1 = -1
              
             if len(location) > 0:
               res2 = event.location.lower().find(location.lower())
             else:
               res2 = -1
            
             if res != -1 or res1 != -1 or res2 != -1:
               counter=1
               self.response.out.write('<tr>')
               #self.response.out.write('<td>%s</td>' % event.key().id())
               #self.response.out.write('<td>%s</td>' % event.author)
               self.response.out.write('<td>%s</td>' % event.eventname)
               #self.response.out.write('<td>%s</td>' % event.description)
               self.response.out.write('<td>%s</td>' % event.date)
               self.response.out.write('<td>%s</td>' % event.location)
               #self.response.out.write('<td>%s</td>' % event.location_cord1)
               #self.response.out.write('<td>%s</td>' % event.location_cord2)
               #self.response.out.write('<td><a href=\"viewevent?eventid=%s\">View</a></td>' % event.key().id())
               self.response.out.write('<td><a href=# onclick=\"CLoad(\'Event Viewer\',\'/viewevent?eventid=%s\')\">View</a></td>' % event.key().id())
               self.response.out.write('</tr>')
        self.response.out.write('</table>')
        if counter == 0:
          self.response.out.write('<h2 class=\"eventtext\">No Results!!</h2>')
        

class AddComment(webapp.RequestHandler):
    def get(self):
        self.response.out.write('Add Comment')
        author = self.request.get('author')
        eventid = self.request.get('eventid')
        comment = self.request.get('comment')
        c = Comments()
        if users.get_current_user():
            c.author = users.get_current_user()
        c.eventid = eventid
        c.comment = comment
        c.put()


class GetComments(webapp.RequestHandler):
    def get(self):
        self.response.out.write('<p>Get Comments</p>')
        # Write the submission form and the footer of the page
        self.response.out.write("""
              <form action="/sign" method="post">
                <div><textarea name="content" rows="3" cols="60"></textarea></div>
                <div><input type="submit" value="Sign Guestbook"></div>
              </form>
            </body>
          </html>""")

        eventid = self.request.get('eventid')
        comments = db.GqlQuery("SELECT * FROM Comments ORDER BY date DESC")
        for comment in comments:
          eid = comment.eventid
          if int(eid) == int(eventid):
            self.response.out.write('<hr>')
            if comment.author:
                self.response.out.write('<b>%s</b> wrote:' % comment.author)
            else:
                self.response.out.write('<b>Duine Eile wrote:</b>')
            self.response.out.write('<p>%s</p>' % comment.comment) 

class AddAtendee(webapp.RequestHandler):
    def get(self):
        self.response.out.write('Add Atendee')
        atendee = self.request.get('atendee')
        eventname = self.request.get('eventname')
        eventid = self.request.get('eventid')
        date = self.request.get('date')
        location = self.request.get('location')
        ea = EventAtendees()
        if users.get_current_user():
            ea.atendee = users.get_current_user()
        ea.eventname = eventname
        ea.eventid = eventid
        ea.date = date
        ea.location = location
        ea.put()

class MyEvents(webapp.RequestHandler):
    def get(self):
        self.response.out.write('<h2>Created Events</h2>')
        ev = db.GqlQuery("SELECT * FROM EventDetails WHERE author = :1", users.get_current_user())
        self.response.out.write('<table border=0 class=\"eventtext\" width=100%>')
        self.response.out.write('<tr class=\"tblheader\"><th>Name</th><th>Event</th><th>Date</th><th>Location</th><th></th></tr>')
        for event in ev:
               self.response.out.write('<tr>')
               self.response.out.write('<td>%s</td>' % event.author)
               self.response.out.write('<td>%s</td>' % event.eventname)
               self.response.out.write('<td>%s</td>' % event.date)
               self.response.out.write('<td>%s</td>' % event.location)
               self.response.out.write('<td><a href=# onclick=\"CLoad(\'Event Viewer\',\'/viewevent?eventid=%s\')\">View</a></td>' % event.key().id())
               self.response.out.write('</tr>')
        self.response.out.write('</table>')

        self.response.out.write('<hr>')
        self.response.out.write('<h2>Attending Events</h2>')
        events = db.GqlQuery("SELECT * FROM EventAtendees WHERE atendee = :1", users.get_current_user())
        self.response.out.write('<table border=0 class=\"eventtext\" width=100%>')
        self.response.out.write('<tr class=\"tblheader\"><th>Name</th><th>Event</th><th>Date</th><th>Location</th><th></th></tr>')
        for event in events:
          self.response.out.write('<tr>')
          self.response.out.write('<td>%s</td>' % event.atendee)
          self.response.out.write('<td>%s</td>' % event.eventname)
          self.response.out.write('<td>%s</td>' % event.date)
          self.response.out.write('<td>%s</td>' % event.location)
          self.response.out.write('<td><a href=# onclick=\"CLoad(\'Event Viewer\',\'/viewevent?eventid=%s\')\">View</a></td>' % event.eventid)
          self.response.out.write('</tr>')
        self.response.out.write('</table>')

        
class ViewEvent(webapp.RequestHandler):
    def get(self):
        eventid = self.request.get('eventid')
        events = db.GqlQuery("SELECT * FROM EventDetails")
        for event in events:
          eid = event.key().id()
          if int(eid) == int(eventid):
            author = event.author
            eventname = event.eventname
            description = event.description
            date = event.date
            location = event.location
            coord1 = event.location_cord1
            coord2 = event.location_cord2

        template_values = {
          'eid': eid,
          'author': author,
          'eventname': eventname,
          'description': description,
          'date': date,
          'location': location,
          'coord1': coord1,
          'coord2': coord2
          }
        template_file = 'ViewEventForm.html'
        path = os.path.join(os.path.dirname(__file__), 'main_templates',template_file)
        self.response.out.write(template.render(path, template_values))

class ViewCalendar(webapp.RequestHandler):
    def get(self):
        events = db.GqlQuery("SELECT * FROM PersonalDetails WHERE uname = :1", users.get_current_user())
        dlink = ""
        for event in events:
          dlink = self.response.out.write('<td>%s</td>' % event.googlelink)
        self.response.out.write(dlink)

class AddEventIframe(webapp.RequestHandler):
    def get(self):
        self.response.out.write("<iframe src=\"http://zaradowfriends.appspot.com/AddEvent\" style=\"border: 0\" width=\"530\" height=\"650\" frameborder=\"0\" scrolling=\"no\"></iframe>")

class Start(webapp.RequestHandler):
    # Initialize some global variables we will use
    def __init__(self):
        # Stores the page's current user
        self.current_user = None
        # Stores the token_scope information
        self.token_scope = None
        # Stores the Google Data Client
        self.client = None
        # The one time use token value from the URL after the AuthSub redirect.
        self.token = None
        # Init local time - default date for new events
        localtime = time.localtime()
        self.todays_date = "%s-%s-%s" % (localtime[0], localtime[1], localtime[2])

    def get(self):
        self.current_user = users.GetCurrentUser()

        if not self.current_user:
          template_values = {
            'login_url': users.CreateLoginURL(self.request.uri),
            'app_name': APP_NAME,
            'css_link': CSS_LINK,
            'app_info': APP_INFO
            }
          template_file = 'login.html'
        else:
          self.token = self.request.get('token')

          # Manage our Authentication for the user
          self.ManageAuth()
          self.LookupToken()
          
          if self.client.GetAuthSubToken() is not None:
            template_values = {
            }
            template_file = 'index.html'
          else:
            template_values = {
              'authsub_url': self.client.GenerateAuthSubURL(
                  'http://%s/' % (HOST_NAME),
                  '%s %s' % ('http://www.google.com/m8/feeds/', 
                      'http://www.google.com/calendar/feeds'),
                  secure=False, session=True),
                  'app_name': APP_NAME,
                  'css_link': CSS_LINK
              }
            template_file = 'authorize_access.html'

        path = os.path.join(os.path.dirname(__file__), 'main_templates', 
            template_file)
        self.response.out.write(template.render(path, template_values))

    def ManageAuth(self):
        self.client = gdata.service.GDataService()
        gdata.alt.appengine.run_on_appengine(self.client)
        if self.token:
          # Upgrade to a session token and store the session token.
          self.UpgradeAndStoreToken()

    def LookupToken(self):
        if self.current_user:
          stored_tokens = StoredToken.gql('WHERE user_email = :1',
              self.current_user.email())
          for token in stored_tokens:
            self.client.SetAuthSubToken(token.session_token)

    def UpgradeAndStoreToken(self):
        self.client.SetAuthSubToken(self.token)
        self.client.UpgradeToSessionToken()
        if self.current_user:
          # Create a new token object for the data store which associates the
          # session token with the requested URL and the current user.
          new_token = StoredToken(user_email=self.current_user.email(), 
              session_token=self.client.GetAuthSubToken())
          
          new_token.put()
          self.redirect('http://%s/' % HOST_NAME)
          
class UserLogin(webapp.RequestHandler):
    def get(self):
        # self.response.out.write('User Login Page')
        user = users.get_current_user()
        if user:
            self.response.out.write('<h2>Hello, ' + user.nickname() + '</h2>')
            self.response.out.write('<h2>Login has been successful!!</h2>')
            self.response.out.write('<h2>Click the links on the Menu Bar above to begin....</h2>')
        else:
            self.redirect(users.create_login_url(self.request.uri))

          
class UserManagement(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            self.redirect('/register')
        else:
            self.redirect(users.create_login_url(self.request.uri))

class GetRegistrationDetails(webapp.RequestHandler):
    def get(self):
        template_values = {
        }
        template_file = 'RegistrationForm.html'
        path = os.path.join(os.path.dirname(__file__), 'main_templates',template_file)
        self.response.out.write(template.render(path, template_values))
        
class SetRegistrationDetails(webapp.RequestHandler):
    def post(self):
        pd = PersonalDetails()

        if users.get_current_user():
            pd.uname = users.get_current_user()

        pd.firstname = self.request.get('firstname')
        pd.surname = self.request.get('surname')
        pd.address1 = self.request.get('address1')
        pd.address2 = self.request.get('address2')
        pd.town = self.request.get('town')
        pd.county = self.request.get('county')
        pd.phone = self.request.get('phone')
        pd.desc = self.request.get('desc')
        pd.googlelink = self.request.get('callink')
        pd.put()
        self.response.out.write('<h2 align=center>Registration Complete!</h2>')

class CheckLogin(webapp.RequestHandler):
    def get(self):
        self.response.out.write("<iframe src=\"http://zaradowfriends.appspot.com/UserManagement\" style=\"border: 0\" width=\"530\" height=\"650\" frameborder=\"0\" scrolling=\"no\"></iframe>")

class GetLogin(webapp.RequestHandler):
    def get(self):
        self.response.out.write("<iframe src=\"http://zaradowfriends.appspot.com/UserLogin\" style=\"border: 0\" width=\"530\" height=\"650\" frameborder=\"0\" scrolling=\"no\"></iframe>")
           
def main():
    application = webapp.WSGIApplication(
                                      [('/', Start),('/ViewCal', ViewCalendar),
                                       ('/CheckLogin', CheckLogin),
                                       ('/UserManagement', UserManagement),
                                       ('/UserLogin', UserLogin),
                                       ('/GetLogin', GetLogin),
                                       ('/sign', SetRegistrationDetails),
                                       ('/register', GetRegistrationDetails),
                                       ('/Atendee', UserAddCalendar),
                                       ('/AddComment', AddComment),
                                       ('/AddAtendee', AddAtendee),
                                       ('/GetComment', GetComments),
                                       ('/AddEvent', CalendarContacts),
                                       ('/AddEventFrame', AddEventIframe),
                                       ('/AddUser', UserAddCalendar),
                                       ('/search', SearchEvents),
                                       ('/events', ListEvents),
                                       ('/MyEvents', MyEvents),
                                       ('/viewevent', ViewEvent)],
                                      debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
