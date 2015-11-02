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
import json
from salts_lib import kodi
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import FORCE_NO_MATCH
from salts_lib.constants import QUALITIES

BASE_URL = 'http://yify.tv'
MAX_TRIES = 3

class YIFY_Scraper(scraper.Scraper):
    base_url = BASE_URL

    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = kodi.get_setting('%s-base_url' % (self.get_name()))

    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.MOVIE])

    @classmethod
    def get_name(cls):
        return 'yify.tv'

    def resolve_link(self, link):
        url = '/player/pk/pk/plugins/player_p2.php'
        url = urlparse.urljoin(self.base_url, url)
        data = {'url': link, 'sou': 'pic', 'fv': '11'}
        headers = {'Referer': ''}
        html = ''
        stream_url = None
        tries = 1
        while tries <= MAX_TRIES:
            html = self._http_get(url, data=data, headers=headers, cache_limit=0)
            log_utils.log('Initial Data (%s): |%s|' % (tries, html), log_utils.LOGDEBUG)
            if html.strip():
                break
            tries += 1
        else:
            return None

        try:
            js_data = json.loads(html)
            if 'captcha' in js_data[0]:
                tries = 1
                while tries <= MAX_TRIES:
                    data['type'] = js_data[0]['captcha']
                    captcha_result = self._do_recaptcha(js_data[0]['k'], tries, MAX_TRIES)
                    data['chall'] = captcha_result['recaptcha_challenge_field']
                    data['res'] = captcha_result['recaptcha_response_field']
                    html = self._http_get(url, data=data, headers=headers, cache_limit=0)
                    log_utils.log('2nd Data (%s): %s' % (tries, html), log_utils.LOGDEBUG)
                    if html:
                        js_data = json.loads(html)
                        if 'captcha' not in js_data[0]:
                            break
                    tries += 1
                else:
                    return None

            best_width = 0
            for elem in js_data:
                if 'type' in elem and elem['type'].startswith('video') and elem['width'] > best_width:
                    stream_url = elem['url']
                    best_width = elem['width']
                if 'jscode' in elem:
                    stream_url = self.__parse_fmt(elem['jscode'])
                    break
        except ValueError:
            return None

        return stream_url

    def __parse_fmt(self, js_data):
        sources = {}
        formats = {}
        match = re.search('\("(.*?)"\)', js_data)
        if match:
            params = match.group(1)
            for match in re.finditer('&?([^=]+)=([^&$]+)', params):
                key, value = match.groups()
                value = urllib.unquote(value)
                if key == 'fmt_stream_map':
                    items = value.split(',')
                    for item in items:
                        source_fmt, source_url = item.split('|')
                        sources[source_url] = source_fmt
                elif key == 'fmt_list':
                    items = value.split(',')
                    for item in items:
                        format_key, q_str, _ = item.split('/', 2)
                        w, _ = q_str.split('x')
                        formats[format_key] = int(w)

        best_width = 0
        best_source = None
        for source in sources:
            if sources[source] in formats:
                if formats[sources[source]] >= best_width:
                    best_width = formats[sources[source]]
                    best_source = source

        return best_source

    def format_source_label(self, item):
        return '[%s] %s (%s views)' % (item['quality'], item['host'], item['views'])

    def get_sources(self, video):
        source_url = self.get_url(video)
        hosters = []
        if source_url and source_url != FORCE_NO_MATCH:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)

            match = re.search('class="votes">(\d+)</strong>', html)
            views = None
            if match:
                views = int(match.group(1))

            for match in re.finditer('pic=([^&]+)', html):
                video_id = match.group(1)
                hoster = {'multi-part': False, 'host': 'yify.tv', 'class': self, 'quality': QUALITIES.HD720, 'views': views, 'rating': None, 'url': video_id, 'direct': True}
                hosters.append(hoster)
        return hosters

    def get_url(self, video):
        return super(YIFY_Scraper, self)._default_get_url(video)

    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/?no&order=desc&years=%s&s=' % (year))
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=.25)
        results = []
        pattern = 'var\s+posts\s*=\s*(.*);'
        match = re.search(pattern, html)
        if match:
            fragment = match.group(1)
            if fragment and fragment != 'null':
                try:
                    data = json.loads(fragment)
                    for post in data['posts']:
                        result = {'title': post['title'], 'year': post['year'], 'url': post['link'].replace(self.base_url, '')}
                        results.append(result)
                except ValueError:
                    log_utils.log('Invalid JSON in yify.tv: %s' % (fragment), log_utils.LOGWARNING)
        return results
