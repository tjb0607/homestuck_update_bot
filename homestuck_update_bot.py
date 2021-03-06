#!/usr/bin/python
from operator import itemgetter, attrgetter
import praw
import feedparser
import time
import http.client
import urllib.request
import warnings
import html
import html.parser
from datetime import datetime, date
from ircbot import *
from multiprocessing import Process

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
    
    def __init__(self, user_agent, usr, pss, rss, sr, channel, refresh):
        super().__init__(user_agent)
        self.usr = usr
        self.pss = pss
        self.rss = rss
        self.sr = sr
        self.channel = channel
        self.refresh = refresh
        self.next_page_number = 0
        
        self.tryLogin(self.usr, self.pss)
        
        self.updateLatestPage(important=True)
        #self.next_page_number -= 2 ##DEBUG##
        
    def tryLogin(self, Username, Password):
        tsPrint('[ INFO] Logging in as ' + Username + '...')
        self.login(Username, Password)
        if (self.is_logged_in() == False):
            tsPrint('[ALERT] Login fail as ' + Username)
            time.sleep(30)
            self.tryLogin(Username, Password)
        tsPrint('[LOGIN] Logged in as ' + Username)

    def updateLatestPage(self, important=False, fast=False):
        tsPrint('[ INFO] Finding latest page...')
        
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
            tsPrint('[ INFO] Latest page info is wrong')
            if important == True:
                tsPrint('[ INFO] Trying again after 30s...')
                time.sleep(30)
                self.updateLatestPage(important=True)
                return
            else:
                self.next_page_number = 0
                return False
        
        #just in case the rss feed is behind
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            status = getStatusCode('www.mspaintadventures.com', '/6/' + str(self.next_page_number).zfill(6) + '.txt')
            if status != 404:
                tsPrint('[ INFO] Next page number (' + str(self.next_page_number) + ') is either behind or not responding. Finding by counting...')
                tsPrint('[ INFO] ' + str(self.next_page_number) + ': ' + str(status))
                while (status != 404):
                    if (status == 200) or (status == 302):
                        self.next_page_number += 1
                    else:
                        tsPrint('[ERROR] status wasn\'t 200, 302, or 404')
                        if important:
                            time.sleep(3)
                        else:
                            self.next_page_number = 0
                            break
                    time.sleep(0.025)
                    if fast == False:
                        time.sleep(1.9)
                    status = getStatusCode('www.mspaintadventures.com', '/6/' + str(self.next_page_number).zfill(6) + '.txt')
                    tsPrint('[ INFO] ' + str(self.next_page_number) + ': ' + str(status))

        tsPrint('[ INFO] Found latest page: http://www.mspaintadventures.com/?s=6&p=' + str(self.next_page_number - 1).zfill(6))
        return True

    def checkMspa(self):
        tsPrint('[ INFO] Checking for upd8 at http://www.mspaintadventures.com/6/' + str(self.next_page_number).zfill(6) + '.txt')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            status = getStatusCode('www.mspaintadventures.com', '/6/' + str(self.next_page_number).zfill(6) + '.txt')
        if (status == 200) or (status == 302):
            link = 'http://www.mspaintadventures.com/?s=6&p=' + str(self.next_page_number).zfill(6)
            tsPrint('[ INFO] Upd8 found! ' + link)
            response = urllib.request.urlopen('http://www.mspaintadventures.com/6/' + str(self.next_page_number).zfill(6) + '.txt')
            txt = response.read().decode('utf-8')
            if sys.version_info[0] == 3 and sys.version_info[1] <= 3:
                title = html.parser.HTMLParser().unescape(txt.split('\n')[0])
            else:
                title = html.unescape(txt.split('\n')[0])
                
            p = Process(target=quickIrcMsg, args=("irc.synirc.net", self.channel, self.usr, self.pss, "New item in the feed homestuck: " + title + " <" + link + ">", "anyway later"))
            p.start()
            tsPrint('[ INFO] IRC bot running in background')

            f = open("/var/www/upd8/check.js", "w")
            f.write('showupd8("' + str(self.next_page_number).zfill(6) + '", "' + title + '");\n')
            f.close()

            if (self.is_logged_in() == False):
                self.tryLogin(self.usr, self.pss)
                
            try:
                page_number = self.next_page_number
                self.updateLatestPage(important=False, fast=True)
                pages = self.next_page_number - page_number
                if pages == 1:
                    tsPrint('[ INFO] Upd8 is 1 page')
                    submission = self.submit(self.sr, '[UPDATE %d - 1 page] %s' % (page_number, title), url=link)
                elif pages >= 1:
                    tsPrint('[ INFO] Upd8 is ' + str(pages) + ' pages')
                    submission = self.submit(self.sr, '[UPDATE %d - %d pages] %s' % (page_number, pages, title), url=link)
                else:
                    submission = self.submit(self.sr, '[UPDATE %d] %s' % (page_number, title), url=link)
                tsPrint('[ POST] Posted to reddit! ' + submission.short_link)
                 tsPrint('[ POST] Posted to reddit! ' + submission.short_link)
                f = open("/var/www/upd8/latestpage.txt", "w")
                f.write(str(self.next_page_number - 1) + '\n')
                f.close()
            except praw.errors.AlreadySubmitted:
                results = self.search('subreddit:\'' + sr + '\' url:\'' + e.link + '\'', sort='new')
                submission = next(results)
                tsPrint('[ALERT] Already posted. ' + submission.short_link)
            except:
                tsPrint('[ALERT] Unexpected exception: ' + str(sys.exc_info()[0]))
                time.sleep(600)

            tsPrint('[SLEEP] Sleeping for 10m...')
            time.sleep(600)
            
            f = open("/var/www/upd8/check.js", "w")
            f.write('shownoupd8();\n')
            f.close()
            
            self.updateLatestPage()
        else:
            tsPrint('[ INFO] %s' % status)
            if (status == None):
                self.checkMspa()

    def run(self):
        while(True):
            if self.next_page_number >= 1901:
                self.checkMspa()
                tsPrint('[SLEEP] Sleeping for %ds...' % self.refresh)
                time.sleep(self.refresh)
            else:
                self.updateLatestPage(important=True)

#Main#
if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",category=DeprecationWarning)
        
        bot = MSPABot(user_agent = 'nice',
                      usr = 'homestuck_update_bot',
                      pss = '',
                      rss = 'http://www.mspaintadventures.com/rss/rss.xml',
                      #sr = 'GrGws7QfBU98Yb40JYFY',
                      #channel = '#bottest',
                      sr = 'homestuck',
                      channel = '#homestuck',
                      refresh = 5)
        bot.run()
