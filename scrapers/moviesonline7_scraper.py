"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import scraper
import urllib
import urlparse
import re
from salts_lib import kodi
from salts_lib import dom_parser
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

BASE_URL = 'http://moviesonline7.co'
BUY_VIDS_URL = '/includes/buyVidS.php?vid=%s&num=%s'
QUALITY_MAP = {'BRRIP1': QUALITIES.HIGH, 'BRRIP2': QUALITIES.HD720, 'BRRIP3': QUALITIES.MEDIUM, 'BRRIP4': QUALITIES.HD720,
               'DVDRIP1': QUALITIES.HIGH, 'DVDRIP2': QUALITIES.HIGH, 'DVDRIP3': QUALITIES.HIGH,
               'CAM1': QUALITIES.LOW, 'CAM2': QUALITIES.LOW}

class MO7_Scraper(scraper.Scraper):
    base_url = BASE_URL

    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = kodi.get_setting('%s-base_url' % (self.get_name()))

    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.MOVIE])

    @classmethod
    def get_name(cls):
        return 'MoviesOnline7'

    def resolve_link(self, link):
        html_url = self._http_get(link, cache_limit=.5)
        if html_url:
            html = self._http_get(html_url, cache_limit=.5)
            match = re.search("'file'\s*,\s*'([^']+)", html)
            if match:
                host = urlparse.urlparse(html_url).hostname
                stream_url = 'http://' + host + match.group(1)
                return stream_url

    def format_source_label(self, item):
        return '[%s] %s' % (item['quality'], item['host'])

    def get_sources(self, video):
        source_url = self.get_url(video)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)

            quality = QUALITIES.HIGH
            match = re.search("kokybe;([^']+)", html)
            if match:
                quality = QUALITY_MAP.get(match.group(1).upper(), QUALITIES.HIGH)

            match = re.search("buyVid\('(\d+)", html)
            if match:
                vid_num = match.group(1)
                match = re.search('n(\d+)\.html', source_url)
                if match:
                    stream_url = urlparse.urljoin(self.base_url, BUY_VIDS_URL % (match.group(1), vid_num))
                    if stream_url:
                        hoster = {'multi-part': False, 'host': self._get_direct_hostname(stream_url), 'url': stream_url, 'class': self, 'rating': None, 'views': None, 'quality': quality, 'direct': True}
                        hosters.append(hoster)

        return hosters

    def get_url(self, video):
        return super(MO7_Scraper, self)._default_get_url(video)

    def search(self, video_type, title, year):
        results = []
        search_url = urlparse.urljoin(self.base_url, '/search.php?stext=')
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=.25)
        for cell in dom_parser.parse_dom(html, 'table', {'class': 'boxed'}):
            url = dom_parser.parse_dom(cell, 'a', ret='href')
            match_title = dom_parser.parse_dom(cell, 'h3', {'class': 'title_grid'})
            if url and match_title:
                url = url[0].replace(self.base_url, '')
                if not url.startswith('/'): url = '/' + url
                result = {'url': url, 'title': match_title[0], 'year': ''}
                results.append(result)

        return results

    def _http_get(self, url, data=None, cache_limit=8):
        return super(MO7_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, data=data, cache_limit=cache_limit)
