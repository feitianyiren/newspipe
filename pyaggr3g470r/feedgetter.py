#! /usr/bin/env python
#-*- coding: utf-8 -*-

# pyAggr3g470r - A Web based news aggregator.
# Copyright (C) 2010-2013  Cédric Bonhomme - http://cedricbonhomme.org/
#
# For more information : http://bitbucket.org/cedricbonhomme/pyaggr3g470r/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

__author__ = "Cedric Bonhomme"
__version__ = "$Revision: 2.0 $"
__date__ = "$Date: 2010/09/02 $"
__revision__ = "$Date: 2013/11/10 $"
__copyright__ = "Copyright (c) Cedric Bonhomme"
__license__ = "GPLv3"

import threading

import feedparser
from BeautifulSoup import BeautifulSoup
from datetime import datetime

import models
import conf
import search
import utils

from flask.ext.mail import Message
from pyaggr3g470r import app, mail

#import log
#pyaggr3g470r_log = log.Log()

list_of_threads = []

class FeedGetter(object):
    """
    This class is in charge of retrieving feeds listed in ./var/feed.lst.
    This class uses feedparser module from Mark Pilgrim.
    For each feed a new thread is launched.
    """
    def __init__(self, email):
        """
        Initializes the database connection.
        """
        #feedparser.USER_AGENT = conf.USER_AGENT
        feedparser.USER_AGENT = "pyAggr3g470r"
        self.user = models.User.objects(email=email).first()

    def retrieve_feed(self):
        """
        Parse the file 'feeds.lst' and launch a thread for each RSS feed.
        """
        for current_feed in [feed for feed in self.user.feeds if feed.enabled]:
            try:
                # launch a new thread for the RSS feed
                thread = threading.Thread(None, self.process, \
                                           None, (current_feed, ))
                thread.start()
                list_of_threads.append(thread)
            except:
                pass

        # wait for all threads are done
        for th in list_of_threads:
            th.join()

    def process(self, feed):
        """
        Retrieves articles form the feed and add them to the database.
        """
        #a_feed = feedparser.parse(feed_link, handlers = [self.proxy])
        a_feed = feedparser.parse(feed.link)
        if a_feed['entries'] == []:
            return

        articles = []
        for article in a_feed['entries']:

            if models.Article.objects(link=article.link).first() != None:
                # if article already in the database continue with the next article
                continue

            description = ""
            article_title = ""
            try:
                # article content
                description = article.content[0].value
            except AttributeError:
                try:
                    # article description
                    description = article.description
                except Exception:
                    description = ""
            try:
                description = BeautifulSoup(description, "html.parser").decode()
                article_title = BeautifulSoup(article.title, "html.parser").decode()
            except Exception as E:
                #pyaggr3g470r_log.error("Problem when sanitizing the content of the feed: " + feed.link)
                article_title = article.title

            try:
                post_date = datetime(*article.published_parsed[:6])
            except:
                post_date = datetime(*article.updated_parsed[:6])

            # save the article
            article = models.Article(post_date, article.link, article_title, description, False, False)
            article.save()
            articles.append(article)

            # add the article to the Whoosh index
            try:
                search.add_to_index([article], feed)
            except Exception as e:
                print("Whoosh error: " + str(e))
                #pyaggr3g470r_log.error("Whoosh error.")
                continue

            # email notification
            if conf.MAIL_ENABLED and feed.email_notification:
                with app.app_context():
                    msg = Message('[pyAggr3g470r] ' + feed.title + ' : ' + article.title, \
                                sender = conf.MAIL_FROM, recipients = [conf.MAIL_TO])
                    msg.body = utils.clear_string(description)
                    msg.html = description
                    mail.send(msg)

        # add the articles to the list of articles for the current feed
        feed.articles.extend(articles)
        feed.articles = sorted(feed.articles, key=lambda t: t.date, reverse=True)
        self.user.save()


if __name__ == "__main__":
    # Point of entry in execution mode
    feed_getter = FeedGetter()
    # Retrieve all feeds
    feed_getter.retrieve_feed()