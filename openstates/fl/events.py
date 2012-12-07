import re
import datetime

from billy.scrape.events import EventScraper, Event

import pytz
import feedparser


class FLEventScraper(EventScraper):
    jurisdiction = 'fl'

    _tz = pytz.timezone('US/Eastern')

    def scrape(self, chamber, session):
        if chamber == 'upper' and session == '2011':
            self.scrape_upper_events(session)

    def scrape_upper_events(self, session):
        url = "http://flsenate.gov/Session/DailyCalendarRSS.cfm?format=rss"
        with self.urlopen(url) as page:
            feed = feedparser.parse(page)

            for entry in feed['entries']:
                if 'Committee' not in entry['summary']:
                    continue

                date = datetime.datetime(*entry['updated_parsed'][:6])
                match = re.match(r'(\d+):(\d+)', entry['title'])
                if match:
                    when = datetime.datetime(date.year, date.month,
                                             date.day,
                                             int(match.group(1)),
                                             int(match.group(2)),
                                             0)
                    when = self._tz.localize(when)

                    desc = entry['summary'].split(' - ')[0]
                    location = entry['summary'].split(' - ')[1]

                    event = Event(session, when, 'committee:meeting',
                                  desc, location)
                    event.add_source(url)

                    self.save_event(event)
