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
import re
import urllib
import urlparse
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

QUALITY_MAP = {'DVD': QUALITIES.HIGH, 'TS': QUALITIES.MEDIUM, 'CAM': QUALITIES.LOW}
BASE_URL = 'http://www.primewire.ag'

class PW_Scraper(scraper.Scraper):
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        base_url = self.db_connection.get_setting('%s_base_url' % (self.get_name()))
        if not base_url:
            self.base_url = BASE_URL
        else:
            self.base_url = base_url
   
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])
    
    @classmethod
    def get_name(cls):
        return 'PrimeWire'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        label='[%s] %s (%s views) (%s/100) ' % (item['quality'], item['host'], item['views'], item['rating'])
        if item['verified']: label = '[COLOR yellow]%s[/COLOR]' % (label)
        return label
    
    def get_sources(self, video_type, title, year, season='', episode=''):
        source_url=self.get_url(video_type, title, year, season, episode)
        hosters = []
        if source_url:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self.__http_get(url, cache_limit=.5)
            
            container_pattern = r'<table[^>]+class="movie_version[ "][^>]*>(.*?)</table>'
            item_pattern = (
                r'quality_(?!sponsored|unknown)([^>]*)></span>.*?'
                r'url=([^&]+)&(?:amp;)?domain=([^&]+)&(?:amp;)?(.*?)'
                r'"version_veiws"> ([\d]+) views</')
            max_index=0
            max_views = -1
            for container in re.finditer(container_pattern, html, re.DOTALL | re.IGNORECASE):
                for i, source in enumerate(re.finditer(item_pattern, container.group(1), re.DOTALL)):
                    qual, url, host, parts, views = source.groups()
             
                    item = {'host': host.decode('base-64'), 'url': url.decode('base-64')}
                    item['verified'] = source.group(0).find('star.gif') > -1
                    item['quality'] = QUALITY_MAP.get(qual.upper())
                    item['views'] = int(views)
                    if item['views'] > max_views:
                        max_index=i
                        max_views=item['views']
                        
                    item['rating'] = item['views']*100/max_views
                    pattern = r'<a href=".*?url=(.*?)&(?:amp;)?.*?".*?>(part \d*)</a>'
                    other_parts = re.findall(pattern, parts, re.DOTALL | re.I)
                    if other_parts:
                        item['multi-part'] = True
                        item['parts'] = [part[0].decode('base-64') for part in other_parts]
                    else:
                        item['multi-part'] = False
                    item['class']=self
                    hosters.append(item)
            
            for i in xrange(0,max_index):
                hosters[i]['rating']=hosters[i]['views']*100/max_views
         
        return hosters

    def get_url(self, video_type, title, year, season='', episode=''):
        return super(PW_Scraper, self)._default_get_url(video_type, title, year, season, episode)
    
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/index.php?search_keywords=')
        search_url += urllib.quote_plus(title)
        search_url += '&year=' + urllib.quote_plus(str(year))
        if video_type in [VIDEO_TYPES.TVSHOW, VIDEO_TYPES.EPISODE]:
            search_url += '&search_section=2'
        else:
            search_url += '&search_section=1'
            
        html = self. __http_get(self.base_url, cache_limit=0)
        r = re.search('input type="hidden" name="key" value="([0-9a-f]*)"', html).group(1)
        search_url += '&key=' + r
        
        html = self.__http_get(search_url, cache_limit=.25)
        pattern = r'class="index_item.+?href="(.+?)" title="Watch (.+?)"?\(?([0-9]{4})?\)?"?>'
        results=[]
        for match in re.finditer(pattern, html):
            result={}
            url, title, year = match.groups('')
            result['url']=url
            result['title']=title
            result['year']=year
            results.append(result)
        return results
    
    def _get_episode_url(self, show_url, season, episode):
        url = urlparse.urljoin(self.base_url, show_url)
        html = self.__http_get(url, cache_limit=2)
        pattern = '"tv_episode_item".+?href="([^"]+/season-%s-episode-%s)">' % (season, episode)
        match = re.search(pattern, html, re.DOTALL)
        if match:
            return match.group(1)
        
    def __http_get(self, url, cache_limit=8):
        return super(PW_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
