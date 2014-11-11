#!/usr/bin/python
from operator import itemgetter, attrgetter
from datetime import datetime, date
import praw
import feedparser
import time
import http.client
import urllib.request
import warnings
import html

#Print with timestamp
def tsPrint(message):
    ts = time.time()
    st = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
    print(st + ' ' + message)
    
#Get status code
def getStatusCode(host, path="/"):
    try:
        conn = http.client.HTTPConnection(host, 80, timeout=10)
        conn.request("HEAD", path, headers={'Connection': 'close'})                                                                                         
        return conn.getresponse().status
    except:
        return None

class RssParseError(Exception):
    def __init__(self, message = ''):
        self.message = message
    def __str__(self):
        return repr(self.message)

class MSPABot(praw.Reddit):
    
    def __init__(self, user_agent, usr, pss, rss, sr, refresh):
        super().__init__(user_agent)
        self.usr = usr
        self.pss = pss
        self.rss = rss
        self.sr = sr
        self.refresh = refresh
        self.next_page_number = 0
        
        self.tryLogin(self.usr, self.pss)
        
        self.updateLatestPage()
        
    def tryLogin(self, Username, Password):
        self.login(Username, Password)
        if (self.is_logged_in() == False):
            tsPrint('[ALERT] Login fail as ' + Username)
            time.sleep(30)
            self.tryLogin(Username, Password)
            return
        tsPrint('[LOGIN] Logged in as ' + Username)

    def updateLatestPage(self):
        
        tsPrint('[ INFO] Finding latest page')
        
        try:
            feed = feedparser.parse(self.rss)
            if (feed.entries == []):
                try:
                    raise RssParseError('Error while fetching feed: ' + str(feed.bozo_exception))
                except AttributeError:
                    raise RssParseError('Unknown error while fetching feed')
            
            #get rid of that god damn hscroll test
            i = 0
            for entry in feed.entries:
                if(entry.published == ''):
                    del feed.entries[i]
                i += 1
            
            try:
                sorted_entries = sorted(feed.entries, key=attrgetter('published_parsed'))
            except TypeError as e:
                raise RssParseError('Error sorting feed: ' + str(e))
            latest_entry = sorted_entries[len(sorted_entries)-1]
            page_link = latest_entry.link
            
            try:
                next_page_number = int(page_link[-6:]) + 1
            except ValueError:
                raise RssParseError('Bad MSPA URL (' + page_link + ')')
            
            if (self.next_page_number < next_page_number):
                self.next_page_number = next_page_number
        except RssParseError as e:
            tsPrint('[ALERT] RSS exception: ' + e.message)
        except:
            tsPrint('[ALERT] Unexpected RSS exception: ' + str(sys.exc_info()[0]))
        
        if (self.next_page_number < 1901):
            tsPrint('[ INFO] Trying again after 30s...')
            time.sleep(30)
            self.updateLatestPage()
            return
        
        #just in case the rss feed is behind
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            status = getStatusCode('www.mspaintadventures.com', '/6/' + str(self.next_page_number).zfill(6) + '.txt')
            if status != 404:
                tsPrint('[ INFO] Next page number (' + str(self.next_page_number) + ') is either behind or not responding. Finding by counting.')
                tsPrint('[ INFO] ' + str(self.next_page_number) + ': ' + str(status))
                while (status != 404):
                    if status == 200:
                        self.next_page_number += 1
                    time.sleep(2)
                    status = getStatusCode('www.mspaintadventures.com', '/6/' + str(self.next_page_number).zfill(6) + '.txt')
                    tsPrint('[ INFO] ' + str(self.next_page_number) + ': ' + str(status))

        tsPrint('[ INFO] Found latest page: http://www.mspaintadventures.com/?s=6&p=' + str(self.next_page_number - 1).zfill(6))

    def checkMspa(self):
        tsPrint('[ INFO] Checking for upd8...')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            status = getStatusCode('www.mspaintadventures.com', '/6/' + str(self.next_page_number).zfill(6) + '.txt')
        if (status == 200):
            link = 'http://www.mspaintadventures.com/?s=6&p=' + str(self.next_page_number).zfill(6)
            tsPrint('[ INFO] Upd8 found! ' + link)
            response = urllib.request.urlopen('http://www.mspaintadventures.com/6/' + str(self.next_page_number).zfill(6) + '.txt')
            txt = response.read().decode('utf-8')
            title = html.unescape(txt.split('\n')[0])
            if (self.is_logged_in() == False):
                self.tryLogin(self.usr, self.pss)
            try:
                submission = self.submit(self.sr, '[UPDATE %d] %s' % (self.next_page_number, title), url=link)
                tsPrint('[ POST] Posted to reddit! ' + submission.short_link)
            except praw.errors.AlreadySubmitted:
                tsPrint('[ALERT] Already posted')
            
            tsPrint('[SLEEP] Sleeping for 10m...')
            time.sleep(600)
            
            self.updateLatestPage()
            
        else:
            tsPrint('[ INFO] %s' % status)
            if (status == None):
                time.sleep(1)
                self.checkMspa()
                return

    def run(self):
        while(True):
            try:
                self.checkMspa()
                tsPrint('[SLEEP] Sleeping for %ds...' % self.refresh)
                time.sleep(self.refresh)
            except:
                tsPrint('[ALERT] Exception: ', sys.exc_info()[0])
                time.sleep(5)
                pass

if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",category=DeprecationWarning)
        
        bot = MSPABot(user_agent = 'RSS Bot for /r/Homestuck',
                      usr = 'homestuck_update_bot',
                      pss = '',
                      rss = 'http://www.mspaintadventures.com/rss/rss.xml',
                      sr = 'homestuck',
                      refresh = 5)
        bot.run()
