#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""phpBB to static HTML converter.

A Python script to migrate a phpBB 3 forum into static HTML pages.

CAUTION: Make a backup of both your phpBB database before running this tool.
USE IS ENTIRELY AT YOUR OWN RISK.

First released 2015-11-29 by
Anthony Lopez-Vito of Another Cup of Coffee Limited
http://anothercoffee.net

All code is released under The MIT License. Please see LICENSE.txt.

MySQL queries are based on the queries from the phpBB2HTML script. That script
didn't work for me so I wrote my own version in Python.
"""

import sys, getopt, os
import MySQLdb as mdb
from MySQLdb import OperationalError
from contextlib import closing
import logging, logging.handlers
from datetime import datetime
import cgi
import yaml
from jinja2 import Environment, FileSystemLoader


logger = logging.getLogger()


def get_settings():
    """Get settings from external YAML file
    """
    settings = {}
    try:
        with open("settings.yml", 'r') as ymlfile:
            settings = yaml.load(ymlfile)
    except IOError:
        logger.error("Could not open settings file")
    else:
        logger.debug("Opened settings file")

    return settings


def setup_logging(settings):
    """Log output

        Sends log output to console or file,
        depending on error level
    """
    try:
        log_filename = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            settings['log_filename']
        )
        log_max_bytes = settings['log_max_bytes']
        log_backup_count = settings['log_backup_count']
    except KeyError as ex:
        print "WARNING: Missing logfile setting {}. Using defaults.".format(ex)
        log_filename = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "log.txt"
        )
        log_max_bytes = 1048576 #1MB
        log_backup_count = 5

    logger.setLevel(logging.DEBUG)
    # Set up logging to file
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_filename,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s %(name)-15s %(levelname)-8s %(message)s',
        '%m-%d %H:%M'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Handler to write INFO messages or higher to sys.stderr
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)-8s %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    logger.debug("------------------------------")
    logger.debug(
        "Starting log for session %s",
        datetime.now().strftime("%Y%m%d%H%M%S%f")
    )


def querydb(dbconn, query):
    """Run a MySQL query string.

    Args:
        query (string): MySQL query string.

    Returns:
        results: Results of the query as a list of tuples.
    """
    results = None
    with closing(dbconn.cursor(mdb.cursors.DictCursor)) as cur:
        try:
            cur.execute(query)
            results = cur.fetchall()
        except (mdb.OperationalError, mdb.ProgrammingError), e:
            logging.error("There was a problem while trying to run a query:\n\t%s", e[1])
            logging.error(query)
            cur.close()
            raise
        except mdb.Warning, warn:
            logging.warn("Warning: %s", warn)
            raise
    return results


def create_directory(path):
    """Create a directory.
    
    Args:
        path: Path to the project location.    
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError as e:
            logging.error(
                "Sorry there was a problem creating the directory: %s",
                e.strerror)
            if not path:
                logging.error("The path string is empty")
    else:
        logging.error("The directory %s already exists", path)


def create_index_html(env, categories, forums):
    fname = "export/index.html"
    context = {
        'categories': categories,
        'forums': forums
    }
    with open(fname, 'w') as f:
        html = env.get_template('index.html').render(context)
        f.write(html.encode('utf8'))


def create_forum_html(env, forum_id, forum_name, topics):
    create_directory("export/"+str(forum_id))
    fname = "export/"+str(forum_id)+"/index.html"
    context = {
        'forum_id': forum_id,
        'forum_name': forum_name,
        'topics': topics
    }
    with open(fname, 'w') as f:
        html = env.get_template('forum.html').render(context)
        f.write(html.encode('utf8'))
        logging.info("Writing forum: %s", forum_name)


def create_topic_html(env, forum_id, forum_name, topic_id, posts):
    fname = "export/"+str(forum_id)+"/"+str(topic_id)+".html"
    context = {
        'forum_id': forum_id,
        'forum_name': forum_name,
        'topic_id': topic_id,
        'topic_title': 'topic title',
        'posts': posts
    }
    with open(fname, 'w') as f:
        html = env.get_template('topic.html').render(context)
        f.write(html.encode('utf8'))
        logging.debug("Writing topic: %s", topic_id)


def get_forums(dbconn):
    categories = None
    forums = None
    query = (
        """SELECT forum_id, forum_name
            FROM phpbb_forums WHERE parent_id = 0"""
    )
    try:
        categories = querydb(dbconn, query)
    except mdb.ProgrammingError as Ex:
        logging.error(Ex)

    query = (
        """SELECT
            forum_id,
            parent_id,
            forum_name,
            forum_posts,
            forum_topics,
            forum_last_poster_name,
            DATE_FORMAT(
                FROM_UNIXTIME(forum_last_post_time),
                '%a %b %d, %Y %h:%i %p') as last_post_time,
            CONVERT(forum_desc USING utf8) as forum_description
        FROM phpbb_forums WHERE parent_id > 0"""
    )
    try:
        forums = querydb(dbconn, query)
    except mdb.ProgrammingError as Ex:
        logging.error(Ex)
    
    return categories, forums


def get_forum_topics(dbconn, forum_id):
    topics = None
    forum_name = None
    query = (
        """SELECT forum_name
            FROM phpbb_forums WHERE forum_id =%s """
        % forum_id
    )
    try:
        forum_name = querydb(dbconn, query)
        forum_name = forum_name[0]['forum_name']
    except mdb.ProgrammingError as Ex:
        logging.error(Ex)

    query = (
        """SELECT
            t.forum_id,
            t.topic_id,
            t.topic_title,
            DATE_FORMAT(
                FROM_UNIXTIME(t.topic_time),
                '%%a %%b %%d, %%Y %%h:%%i %%p') as post_time,
            t.topic_replies,
            u.username
        FROM phpbb_topics t 
        LEFT JOIN phpbb_users u ON t.topic_poster=u.user_id
        WHERE t.topic_moved_id = 0 AND t.forum_id = %s
        ORDER BY t.topic_time DESC"""
        % forum_id
    )
    try:
        topics = querydb(dbconn, query)
        logging.info("Found %s topics", len(topics))
    except mdb.ProgrammingError as Ex:
        logging.error(Ex)

    return forum_name, topics


def get_topic_posts(dbconn, topic_id):
    posts=None

    """            DATE_FORMAT(
                FROM_UNIXTIME(p.post_time),
                '%a %b %d, %Y %h:%i %p') as posted_time,
    """
    query = (
        """SELECT
            p.forum_id,
            p.post_id,
            p.poster_id,
            p.post_username,
            u.username,
            DATE_FORMAT(
                FROM_UNIXTIME(p.post_time),
                '%%a %%b %%d, %%Y %%h:%%i %%p') as posted_time,
            p.post_time,
            pt.post_subject,
            pt.post_text,
            pt.bbcode_uid
        FROM phpbb_posts p
        LEFT JOIN phpbb_users u ON p.poster_id=u.user_id
        LEFT JOIN phpbb_posts pt ON p.post_id=pt.post_id
        WHERE p.topic_id=%s ORDER BY p.post_time ASC"""
        % topic_id)
    try:
        posts = querydb(dbconn, query)
    except mdb.ProgrammingError as Ex:
        logging.error(Ex)

    return posts


def main(argv):
    """Process the user's commands.

    Args:
        argv: The command line options.
    """

    settings = get_settings()
    setup_logging(settings['logger'])

    logging.info("Starting")

    try:
        dbconn = mdb.connect(
            settings['phpbb_db']['host'],
            settings['phpbb_db']['username'],
            settings['phpbb_db']['password'],
            settings['phpbb_db']['database'],
            charset='utf8',
            use_unicode=True
        )
    except OperationalError:
        logging.error("Could not access the database. Aborting database creation.")
    else:
        template_path = os.path.dirname(os.path.abspath(__file__))
        env = Environment(
            autoescape=False,
            loader=FileSystemLoader(os.path.join(template_path, 'templates')),
            trim_blocks=False)
        
        # Create the forum index page
        categories, forums = get_forums(dbconn)
        create_directory("export")
        create_index_html(env, categories, forums)
        for forum in forums:
            # Create the topic listing for each forum category
            forum_name, topics = get_forum_topics(dbconn, forum['forum_id'])

            logging.info("Processing forum %s", forum['forum_id'])
            create_forum_html(env, forum['forum_id'], forum_name, topics)
            for topic in topics:
                # Create the posts for each topic
                posts = get_topic_posts(dbconn, topic['topic_id'])
                create_topic_html(
                    env,
                    forum['forum_id'],
                    forum_name,
                    topic['topic_id'],
                    posts
                )
    exit(0)


# Program entry point
if __name__ == "__main__":
    main(sys.argv[1:])
