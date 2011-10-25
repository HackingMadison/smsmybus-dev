import os
import wsgiref.handlers
import logging

from google.appengine.api import memcache
from google.appengine.api.labs import taskqueue
from google.appengine.api.labs.taskqueue import Task
from google.appengine.ext import webapp

import twilio
import config 
from apps import api_bridge

class PhoneRequestStartHandler(webapp.RequestHandler):
    
    def post(self):

      # validate it is in fact coming from twilio
      if config.ACCOUNT_SID == self.request.get('AccountSid'):
        logging.debug("PHONE request was confirmed to have come from Twilio.")
      else:
        logging.error("was NOT VALID.  It might have been spoofed!")
        self.response.out.write("Illegal caller")
        return

      # setup the response to get the recording from the caller
      r = twilio.Response()
      g = r.append(twilio.Gather(action=config.URL_BASE+"phone/listenforbus",
                                 method=twilio.Gather.GET,
                                 timeout=10,
                                 finishOnKey="#"))
      g.append(twilio.Say("Welcome to SMS My Bus!"))
      g.append(twilio.Say("Enter the bus number using the keypad. Press the pound key to submit.", 
                          voice=twilio.Say.MAN,
                          language=twilio.Say.ENGLISH, 
                          loop=1))
      self.response.out.write(r)
        
## end PhoneRequestStartHandler


class PhoneRequestBusHandler(webapp.RequestHandler):
    
    def get(self):
      
      # validate it is in fact coming from twilio
      if config.ACCOUNT_SID == self.request.get('AccountSid'):
        logging.debug("PHONE request was confirmed to have come from Twilio.")
      else:
        logging.error("was NOT VALID.  It might have been spoofed!")
        self.response.out.write(errorResponse("Illegal caller"))
        return

      routeID = self.request.get('Digits')
      if len(routeID) == 1:
        routeID = "0" + routeID
      memcache.add(self.request.get('AccountSid'), routeID)

      # setup the response to get the recording from the caller
      r = twilio.Response()
      g = r.append(twilio.Gather(action=config.URL_BASE+"phone/listenforstop",
                                 method=twilio.Gather.GET,
                                 timeout=5,
                                 numDigits=4,
                                 finishOnKey="#"))
      g.append(twilio.Say("Enter the four digit stop number using the keypad. Press the pound key to submit.", 
                          voice=twilio.Say.MAN,
                          language=twilio.Say.ENGLISH, 
                          loop=1))

      logging.debug("now asking the caller to enter their stop number...")
      self.response.out.write(r)
        
## end PhoneRequestBusHandler
        
class PhoneRequestStopHandler(webapp.RequestHandler):
    
    def get(self):
      
      # validate it is in fact coming from twilio
      if config.ACCOUNT_SID == self.request.get('AccountSid'):
        logging.debug("PHONE request was confirmed to have come from Twilio.")
      else:
        logging.error("was NOT VALID.  It might have been spoofed!")
        self.response.out.write(errorResponse("Illegal caller"))
        return
    
      # pull the route and stopID out of the request body and
      # pad it with a zero on the front if the message forgot 
      # to include it (that's how they are stored in the DB)
      routeID = memcache.get(self.request.get('AccountSid'))
      memcache.delete(self.request.get('AccountSid'))
 
      stopID = self.request.get('Digits')
      if len(stopID) == 3:
        stopID = "0" + stopID
      
      # hack - creating a string out of the details to conform to other interfaces
      requestArgs = "%s %s" % (routeID, stopID)

      ## magic ##
      logging.info('starting the magic... %s' % requestArgs)
      textBody = api_bridge.getarrivals(requestArgs, 1)
      logging.debug('phone results are %s' % textBody)
      
      # create an event to log the event
      task = Task(url='/loggingtask', params={'phone':self.request.get('Caller'),
                                              'inboundBody':requestArgs,
                                              'sid':self.request.get('SmsSid'),
                                              'outboundBody':textBody,})
      task.add('eventlogger')

      # transform the text a smidge so it can be pronounced more easily...
      # 1. strip the colons
      textBody = textBody.replace(':', ' ')
      # 2. add a space between p-and-m and a-and-m
      textBody = textBody.replace('pm', 'p m').replace('am', 'a m')
      logging.debug('transformed results into %s' % textBody)
      
      # setup the response
      r = twilio.Response()
      r.append(twilio.Say(textBody, 
                          voice=twilio.Say.MAN,
                          language=twilio.Say.ENGLISH, 
                          loop=1))
      
      self.response.out.write(r)

## end PhoneRequestStopHandler

            
def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/phone/request', PhoneRequestStartHandler),
                                        ('/phone/listenforbus', PhoneRequestBusHandler),
                                        ('/phone/listenforstop', PhoneRequestStopHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
