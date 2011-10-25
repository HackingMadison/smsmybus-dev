import os
import wsgiref.handlers
import logging

from google.appengine.api import memcache
from google.appengine.api.taskqueue import Task

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import twilio
import config
from apps import api_bridge

class SMSRequestHandler(webapp.RequestHandler):

  def post(self):
  
      # validate it is in fact coming from twilio
      if config.ACCOUNT_SID != self.request.get('AccountSid'):
        logging.error("Inbound request was NOT VALID.  It might have been spoofed!")
        self.response.out.write(errorResponse("Illegal caller"))
        return

      # who called? and what did they ask for?
      phone = self.request.get("From")
      msg = self.request.get("Body")
      logging.info("New inbound request from %s with message, %s" % (self.request.get('From'),msg))

      # look out for the abusers
      if filter_the_abusers(phone):
          # don't reply!
          return
      
      # interrogate the message body to determine what to do      
      if msg.lower().find('invite') > -1:
          # ... an invitation request
          response = sendInvite(self.request)
      else:
          ## magic ##
          response = api_bridge.getarrivals(msg,4)	  

      # create an event to log the request
      task = Task(url='/loggingtask', params={'phone':self.request.get('From'),
                                              'inboundBody':self.request.get('Body'),
                                              'sid':self.request.get('SmsSid'),
                                              'outboundBody':response,})
      task.add('eventlogger')

      # setup the response SMS
      #smsBody = "Route %s, Stop %s" % (routeID, stopID) + "\n" + response 
      r = twilio.Response()
      r.append(twilio.Sms(response))
      self.response.out.write(r)
      return
      
## end SMSRequestHandler


# This function checks a list of known system abusuers and rate
# limits their requests on the system
def filter_the_abusers(caller):
    # filter the troublemakers
    if caller in config.ABUSERS:
        counter = memcache.get(caller)
        if counter is None:
            memcache.set(caller,1)
        elif int(counter) <= 3:
            memcache.incr(caller,1)
        else:
            # create an event to log the quota problem
            task = Task(url='/loggingtask', params={'phone':self.request.get('From'),
                                            'inboundBody':self.request.get('Body'),
                                            'sid':self.request.get('SmsSid'),
                                            'outboundBody':'exceeded quota',})
            task.add('eventlogger')
            return True
    return False
## end


# Create a task to send out the invitation SMS
#
def sendInvite(request):
    
      textBody = "You've been invited to use SMSMyBus to find real-time arrivals for your buses. Text your bus stop to this number to get started.(invited by " 
      textBody += request.get('From') + ')'
      
      # parse the message to extract and format the phone number
      # of the invitee. then create a task to send the message
      smsBody = request.get('Body')
      requestArgs = smsBody.split()
      for r in requestArgs:
          phone = r.replace('(','').replace('}','').replace('-','')
          if phone.isdigit() == True:
            task = Task(url='/sendsmstask', params={'phone':phone,
                                                    'sid':request.get('SmsSid'),
                                                    'text':textBody,})
            task.add('smssender')

      return textBody
    
## end sendInvite()
        
# this handler is intended to send out SMS messages
# via Twilio's REST interface
class SendSMSHandler(webapp.RequestHandler):
    def get(self):
      self.post()
      
    def post(self):
      logging.info("Outbound SMS for ID %s to %s" % 
                   (self.request.get('sid'), self.request.get('phone')))
      account = twilio.Account(config.ACCOUNT_SID, config.ACCOUNT_TOKEN)
      sms = {
             'From' : config.CALLER_ID,
             'To' : self.request.get('phone'),
             'Body' : self.request.get('text'),
             }
      try:
          account.request('/%s/Accounts/%s/SMS/Messages' % (config.API_VERSION, config.ACCOUNT_SID),
                          'POST', sms)
      except Exception, e:
          logging.error("Twilio REST error: %s" % e)
                        
## end SendSMSHandler

def main():
  logging.getLogger().setLevel(logging.INFO)
  application = webapp.WSGIApplication([('/sms/request', SMSRequestHandler),
                                        ('/sms/sendsmstask', SendSMSHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
