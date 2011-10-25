import os
import wsgiref.handlers
import logging

from google.appengine.api import mail
from google.appengine.api.taskqueue import Task

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

from apps import api_bridge
import config

class EmailRequestHandler(webapp.RequestHandler):
    def post(self):

      inbound_message = mail.InboundEmailMessage(self.request.body)
      logging.info("Email request! Sent from %s with message subject %s" % (inbound_message.sender,inbound_message.subject))
      
      body = inbound_message.subject
      logging.debug("email body arguments %s" % body)

      ## magic ##
      response = api_bridge.getarrivals(body,10)
      
      # to make it a little easier to read, add newlines before each route report line
      response = response.replace('Route','\nRoute')
      
      # send back the reply with the results
      header = "Thanks for your request! Here are your results...\n\n"
      footer = "\n\nThank you for using SMSMyBus!\nhttp://www.smsmybus.com"

      # setup the response email
      message = mail.EmailMessage()
      message.sender = config.EMAIL_SENDER_ADDRESS
      message.bcc = config.EMAIL_BCC_ADDRESS
      message.to = inbound_message.sender
      message.subject = 'Your Metro schedule estimates for stop %s' % getStopID(body)
      message.body = header + response + footer
      
      logging.debug('sending results to %s' % message.to)
      message.send()

      # create an event to log the event
      task = Task(url='/loggingtask', params={'phone':inbound_message.sender,
                                              'inboundBody':body,
                                              'sid':'email',
                                              'outboundBody':response,})
      task.add('eventlogger')

      self.response.set_status(200)
      return
      
## end EmailRequestHandler
        
def getStopID(msg):
    request = msg.split()
    if len(request) == 1:
        # assume single argument requests are for a bus stop
        stopID = request[0]
    else:
        stopID = request[1]

    return stopID
    
## end getStopID

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/_ah/mail/.+', EmailRequestHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
