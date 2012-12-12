from billy.scrape import NoDataForPeriod
from billy.scrape.committees import CommitteeScraper, Committee
import lxml.html
import re

class NDCommitteeScraper(CommitteeScraper):
    jurisdiction = 'nd'

    def scrape_committee(self, term, chambers, href, name):
        with self.urlopen(href) as page:
            page = lxml.html.fromstring(page)
        page.make_links_absolute(href)
        members =page.xpath("//div[@class='view-content']"
                            "//a[contains(@href, 'members')]/text()")

        if '/joint/' in href:
            chamber = 'joint'
        elif '/senate/' in href:
            chamber = 'upper'
        elif '/house/' in href:
            chamber = 'lower'
        else:
            print "XXX: Fail! %s" % (href)
            return

        cttie = Committee(chamber, name)

        for member in members:
            cttie.add_member(member)  # XXX: Role isn't exactly right.

        cttie.add_source(href)
        self.save_committee(cttie)

    def scrape(self, term, chambers):
        self.validate_term(term, latest_only=True)

        # figuring out starting year from metadata
        for t in self.metadata['terms']:
            if t['name'] == term:
                start_year = t['start_year']
                break

        root = "http://www.legis.nd.gov/assembly"
        main_url = "%s/%s-%s/committees" % (
            root,
            term,
            start_year
        )

        with self.urlopen(main_url) as page:
            page = lxml.html.fromstring(page)
        page.make_links_absolute(main_url)

        ctties = page.xpath("//div[@class='inside']")[0]
        for a in ctties.xpath(".//a[contains(@href, 'committees')]"):
            self.scrape_committee(term, chambers, a.attrib['href'], a.text)
