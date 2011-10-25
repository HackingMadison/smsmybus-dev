import logging
import time

from google.appengine.api import urlfetch
from django.utils import simplejson

import config


# convenienc method for accessing arrival times via the API
#
def getarrivals(request, result_count=3):

    routeID = None
    stopID = None
    
    # there are two valid formats for requests
    # <route> <stop id> : returns the next bus for that stop
    # <stop id> : returns the next N buses for that stop
    #
    requestArgs = request.split()
    logging.info('request has %s arguments' % str(len(requestArgs)))
    if requestArgs[0].isdigit() == True:
        if len(requestArgs) == 1:
            # assume single argument requests are for a bus stop
            stopID = requestArgs[0]
            if len(stopID) == 3:
                stopID = "0" + stopID
            logging.info('determined stopID is %s' % stopID)
        else:
            # pull the route and stopID out of the request body and
            # pad it with a zero on the front if the message forgot  
            # to include it (that's how they are stored in the DB)
            routeID = requestArgs[0]
            if len(routeID) == 1:
                routeID = "0" + routeID
            logging.info('determined routeID is %s' % routeID)

            stopID = requestArgs[1]
            if len(stopID) == 3:
                stopID = "0" + stopID

        # package up the API web service call and make the request
        #
        url = 'http://www.smsmybus.com/api/v1/getarrivals?key=%s&stopID=%s' % (config.METRO_API_KEY,stopID)
        if routeID is not None:
            url += '&routeID=%s' % routeID

        loop = 0
        done = False
        result = None
        while not done and loop < 2:
            try:
              # go fetch the webpage for this route/stop!
              result = urlfetch.fetch(url)
              done = True;
            except urlfetch.DownloadError:
              logging.error("Error loading page (%s)... sleeping" % loop)
              time.sleep(2)
              loop = loop+1

        if result is None or result.status_code != 200:
            logging.error("Exiting early: error fetching API")
            response = 'Snap! The scheduling service is currently down. Please try again shortly'
        else:
            json_results = simplejson.loads(result.content)
            if json_results is None:
                response = 'Snap! The scheduling service is currently down. Please try again shortly'
            elif json_results['status'] == '-1':
                response = "Hmmm. That's strange. It doesn't look like there are ANY routes at this stop"
            else:
                if len(json_results['stop']['route']) == 0:
                    if routeID is None:
                        response = "Snap! It looks like service has ended for the day at that stop."
                    else:
                        response = "Snap! It looks like service has ended for the day at that stop. Are you sure route %s runs through stop %s?" % (routeID,stopID)
                else:
                    # return the first three results for SMS messages
                    response = 'Stop %s: ' % stopID
                    for i,route in enumerate(json_results['stop']['route']):
                        response += 'Route %s, %s toward %s, ' % (route['routeID'],route['arrivalTime'],route['destination'])
                        if i == (result_count-1):
                            break

    else:
        # bogus request
        response = 'Your message must be either... stopID -or- routeID stopID'

    logging.info('returning results... %s' % response)
    return response
 
## end get_arrivals
