import re
from billy.scrape.legislators import LegislatorScraper, Legislator

import lxml.html
import xlrd

_party_map = {'D': 'Democratic', 'R': 'Republican', 'U': 'Independent'}


class MELegislatorScraper(LegislatorScraper):
    jurisdiction = 'me'

    def scrape(self, chamber, term):
        self.validate_term(term, latest_only=True)

        if chamber == 'upper':
            self.scrape_senators(chamber, term)
        elif chamber == 'lower':
            self.scrape_reps(chamber, term)

    def scrape_reps(self, chamber, term_name):
        url = 'http://www.maine.gov/legis/house/dist_mem.htm'
        with self.urlopen(url) as page:
            page = lxml.html.fromstring(page)
            page.make_links_absolute(url)

            # There are 151 districts
            for district in xrange(1, 152):
                if (district % 10) == 0:
                    path = '/html/body/p[%s]/a[3]' % (district + 4)
                else:
                    path = '/html/body/p[%s]/a[2]' % (district + 4)

                link = page.xpath(path)[0]

                leg_url = link.get('href')
                name = link.text_content()

                if len(name) > 0:
                    if name.split()[0] != 'District':
                        mark = name.find('(')
                        party = name[mark + 1]
                        district_name = name[mark + 3:-1]
                        name = name[15:mark]

                        # vacant
                        if party == "V":
                            continue
                        else:
                            party = _party_map[party]

                        leg = Legislator(term_name, chamber, str(district),
                                         name, party=party, url=leg_url,
                                         district_name=district_name)
                        leg.add_source(url)
                        leg.add_source(leg_url)

                        self.scrape_lower_offices(leg, page, leg_url)
                        self.save_legislator(leg)

    def scrape_lower_offices(self, legislator, list_page, url):
        html = self.urlopen(url)
        doc = lxml.html.fromstring(html)
        xpath = '//b[contains(., "Legislative Web Site:")]/../a/@href'
        url = doc.xpath(xpath)
        if url:
            url = url.pop()

        if 'housedems' in url:
            self.scrape_lower_offices_dem(legislator, doc)

        elif 'house_gop' in url:
            self.scrape_lower_offices_gop(legislator, url)

    def scrape_lower_offices_dem(self, legislator, doc):
        address = doc.xpath('//b[contains(., "Address:")]')[0].tail
        address = address.split(',', 1)
        address = '\n'.join(s.strip() for s in address)

        home_xpath = '//b[contains(., "Home Telephone:")]'
        home_phone = doc.xpath(home_xpath)
        if not home_phone:
            home_xpath = '//b[contains(., "Cell Phone:")]'
            home_phone = doc.xpath(home_xpath)
        if not home_phone:
            home_phone = None
        else:
            home_phone = home_phone.pop().tail

        xpath = '//a[contains(@href, "mailto")]'
        try:
            email = doc.xpath(xpath)[0].attrib['href'][7:]
            legislator['email'] = email
        except IndexError:
            # This beast has no email address.
            email = None

        address = ''.join(address[::-1])
        office = dict(
            name='District Office', type='district',
            phone=home_phone,
            fax=None, email=None,
            address=''.join(address))
        legislator.add_office(**office)

        business_xpath = '//b[contains(., "Business Telephone:")]'
        business_phone = doc.xpath(business_xpath)
        if business_phone:
            business_phone = business_phone[0].tail
            office = dict(
                name='District Office', type='district',
                phone=business_phone,
                fax=None, email=None,
                address=None)
            legislator.add_office(**office)

        # Add the dem main office.
        office = dict(
            name='House Democratic Office',
            type='capitol',
            address='\n'.join(['Room 333, State House',
                     '2 State House Station',
                     'Augusta, Maine 04333-0002']),
            fax=None, email=None,
            phone='(207) 287-1430')
        legislator.add_office(**office)

    def scrape_lower_offices_gop(self, legislator, url):
        # Get the www.maine.gov url.
        html = self.urlopen(url)
        doc = lxml.html.fromstring(html)
        doc.make_links_absolute(url)
        # Handle any meta refresh.
        meta = doc.xpath('//meta')[0]
        attrib = meta.attrib
        if 'http-equiv' in attrib and attrib['http-equiv'] == 'REFRESH':
            _, url = attrib['content'].split('=', 1)
            html = self.urlopen(url)
            doc = lxml.html.fromstring(html)
            legislator.add_source(url)

        xpath = '//a[contains(@href, "mailto")]'
        try:
            email = doc.xpath(xpath)[0].attrib['href'][7:]
            legislator['email'] = email
        except IndexError:
            # This beast has no email address.
            email = None

        xpath = '//*[@id="innersidebarlargefont"]'
        text = doc.xpath(xpath)[0].text_content()

        lines = filter(None, text.strip().splitlines())
        lines = lines[1:-1]
        _ = lines.pop()
        _, phone = lines.pop().split(':', 1)
        phone = phone.strip()
        if not phone.strip():
            phone = None

        address = '\n'.join(lines)

        # Add the district office main office.
        office = dict(
            name='District Office',
            type='district',
            address=address,
            fax=None, email=None,
            phone=phone)
        legislator.add_office(**office)

        # Add the GOP main office.
        office = dict(
            name='House GOP Office',
            type='capitol',
            address='\n'.join(['Room 332, State House',
                     '2 State House Station',
                     'Augusta, Maine 04333-0002']),
            fax=None, email=None,
            phone='(207) 287-1440')
        legislator.add_office(**office)

    def scrape_senators(self, chamber, term):
        session = ((int(term[0:4]) - 2009) / 2) + 124
        url = ('http://www.maine.gov/legis/senate/senators/email/'
               '%sSenatorsList.xls' % session)

        DISTRICT = 1
        FIRST_NAME = 3
        MIDDLE_NAME = 4
        LAST_NAME = 6
        PARTY = 7

        mapping = {
            'district': 1,
            'first_name': 3,
            'middle_name': 4,
            'last_name': 5,
            'suffix': 6,
            'party': 7,
            'resident_county': 8,
            'street_addr': 9,
            'city': 10,
            'zip_code': 12,
            'phone': 13,
            'email': 14,
        }

        fn, result = self.urlretrieve(url)
        wb = xlrd.open_workbook(fn)
        sh = wb.sheet_by_index(0)

        for rownum in xrange(1, sh.nrows):
            # get fields out of mapping
            d = {}
            for field, col_num in mapping.iteritems():
                d[field] = str(sh.cell(rownum, col_num).value)

            full_name = " ".join((d['first_name'], d['middle_name'],
                                  d['last_name'], d['suffix']))
            full_name = re.sub(r'\s+', ' ', full_name).strip()

            address = "{street_addr}\n{city}, ME {zip_code}".format(**d)

            # For matching up legs with votes
            district_name = d['city']

            phone = d['phone']

            district = d['district'].split('.')[0]

            leg_url = 'http://www.maine.gov/legis/senate/bio%02ds.htm' % int(district)

            leg = Legislator(term, chamber, district, full_name,
                             d['first_name'], d['last_name'], d['middle_name'],
                             _party_map[d['party']], suffix=d['suffix'],
                             resident_county=d['resident_county'],
                             office_address=address,
                             office_phone=phone,
                             email=None,
                             district_name=district_name,
                             url=leg_url)
            leg.add_source(url)

            office = dict(
                    name='District Office', type='district', phone=phone,
                    fax=None, email=None,
                    address=''.join(address))

            leg['email'] = d['email']
            leg.add_office(**office)
            self.save_legislator(leg)
