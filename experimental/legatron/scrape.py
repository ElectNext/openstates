import os
import sys
from os.path import dirname, abspath, join
import shutil

from models import Feed
from entities import Extractor

if __name__ == '__main__':

    # The path where the news/blogs code and urls files are located.
    PATH = dirname(abspath(__file__))

    #
    filenames = os.listdir(join(PATH, 'urls'))
    filenames = filter(lambda s: '~' not in s, filenames)

    for urls_filename in filenames:
        abbr = urls_filename.lower().replace('.txt', '')

        # If abbrs are specified on the command line, scrape only those.
        if sys.argv[1:] and (abbr not in sys.argv[1:]):
            continue

        with open(join(PATH, 'urls', urls_filename)) as urls:
            urls = urls.read().splitlines()
            ignored = lambda url: not url.strip().startswith('#')
            urls = filter(ignored, urls)
            urls = filter(None, urls)

        # Path to scraped feed data for this state.
        STATE_FEED_DATA = join('data', 'feeds')

        try:
            shutil.rmtree(STATE_FEED_DATA)
        except OSError:
            pass

        try:
            os.makedirs(STATE_FEED_DATA)
        except OSError:
            pass

        extractor = Extractor(abbr)
        for url in urls:
            feed = Feed(url)
            for entry in feed.entries():
                extractor.process_entry(entry.entry)
                import ipdb;ipdb.set_trace()
                entry.finish_report(abbr)
                entry.save_if_entities_found()
            feed.finish_report()
            feed.save()

