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
        
        tsPrint('[ INFO] Finding latest page')
        feed = feedparser.parse(self.rss)
        if (feed.entries == []):
            try:
                tsPrint('[ALERT] Error while fetching feed: ' + str(feed.bozo_exception))
            except AttributeError:
                tsPrint('[ALERT] Unknown error while fetching feed')
            quit()
        #get rid of that god damn hscroll test
        i = 0
        for entry in feed.entries:
            if(entry.published == ''):
                del feed.entries[i]
            i += 1
        
        sorted_entries = sorted(feed.entries, key=attrgetter('published_parsed'))
        latest_entry = sorted_entries[len(feed.entries)-1]
        page_link = latest_entry.link
        self.next_page_number = int(page_link[-6:]) + 1
        self.updateLatestPage()
        
    def tryLogin(self, Username, Password):
        self.login(Username, Password)
        if (self.is_logged_in() == False):
            tsPrint('[ALERT] Login fail as ' + Username)
            time.sleep(30)
            self.tryLogin(Username, Password)
        tsPrint('[LOGIN] Logged in as ' + Username)

    def updateLatestPage(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            while (getStatusCode('www.mspaintadventures.com', '/6/' + str(self.next_page_number).zfill(6) + '.txt') == 200):
                self.next_page_number += 1
        tsPrint('[ INFO] Latest page: http://www.mspaintadventures.com/?s=6&p=' + str(self.next_page_number - 1).zfill(6))

    def checkMspa(self):
        tsPrint('[ INFO] Checking for upd8...')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            status = getStatusCode('www.mspaintadventures.com', '/6/' + str(self.next_page_number).zfill(6) + '.txt')
        if (status == 200):
            link = 'http://www.mspaintadventures.com/?s=6&p=00' + str(self.next_page_number)
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
                self.checkMspa()

    def run(self):
        while(True):
            self.checkMspa()
            tsPrint('[SLEEP] Sleeping for %ds...' % self.refresh)
            time.sleep(self.refresh)

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
