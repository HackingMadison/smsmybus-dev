import os
import wsgiref.handlers
import logging

from google.appengine.api import memcache
from google.appengine.api.taskqueue import Task
from google.appengine.api import xmpp

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import config
from apps import api_bridge


class XmppHandler(webapp.RequestHandler):
    
    def post(self):
      message = xmpp.Message(self.request.POST)
      logging.info("XMPP request! Sent form %s with message %s" % (message.sender,message.body))

      ## magic ##
      response = api_bridge.getarrivals(message.body,10)

      # to make it a little easier to read, add newlines before each route report line
      response = response.replace('Route','\nRoute')

      # create an event to log the request
      task = Task(url='/loggingtask', params={'phone':message.sender,
                                              'inboundBody':message.body,
                                              'sid':'xmpp',
                                              'outboundBody':response,})
      task.add('eventlogger')

      # reply to the chat request
      message.reply(response)

## end XmppHandler()

        
        
def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/_ah/xmpp/message/chat/', XmppHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
