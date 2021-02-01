from __future__ import unicode_literals

import base64
import re

from .common import InfoExtractor

from ..compat import (
    compat_chr,
    compat_urllib_parse_unquote
)
from ..utils import (
    js_to_json,
    std_headers
)


class HKAnimeBaseInfoExtractor(InfoExtractor):
    def _get_episode_info(self, series_info, episode_no=None):
        info = compat_urllib_parse_unquote(base64.b64decode(series_info))
        info = re.sub(
            r'%u([a-fA-F0-9]{4}|[a-fA-F0-9]{2})',
            lambda m: compat_chr(int(m.group(1), 16)),
            info,
            flags=re.UNICODE)
        episodes = []
        for episode in info.split('#'):
            episodes.append(re.match(r'(.+)\$(.+)', episode).groups())

        if episode_no is None:
            return episodes
        else:
            return episodes[int(episode_no) - 1]

    def _str_split(self, string, split_length=1):
        return filter(None, re.split('(.{1,%d})' % split_length, string))

    def _decode_salt(self, e):
        t = ''
        for ch in e:
            t += str(ord(ch) - 100)
        return int(t)

    def _deobfuscator(self, juicycodes):
        jsCode = juicycodes[0:-3]
        ordSalt = self._decode_salt(juicycodes[-3:])
        jsCode += '==='[:4 - len(jsCode) % 4]
        jsCode = jsCode.replace('_', '+').replace('-', '/')
        obfuscated = base64.b64decode(jsCode)

        ordString = ''
        symbolMap = ['`', '%', '-', '+', '*', '$', '!', '_', '^', '=']
        for symbol in obfuscated:
            try:
                ordString += str(symbolMap.index(chr(symbol)))
            except TypeError:
                ordString += str(symbolMap.index(symbol))

        deobfuscated = ''
        splittedOrd = self._str_split(ordString, 4)
        for elem in splittedOrd:
            deobfuscated += chr(int(elem) % 1000 - ordSalt)

        return deobfuscated

    def _get_video_info_by_id(self, video_id, title):
        # Download iframe
        webpage = self._download_webpage(
            'https://play.hkanime.com/embed/' + video_id + '/',
            video_id,
            headers={
                'User-Agent': std_headers['User-Agent'],
                'Referer': 'https://www.hkanime.com/'
            })

        # Parse JuicyCodes
        juicycodes = self._html_search_regex(
            r'_juicycodes\(\"(.+?)\"\);',
            webpage,
            'juicycodes').replace('"+"', '')
        jsCode = self._deobfuscator(juicycodes)
        jwplayer_options = self._html_search_regex(
            r' = (.+?);',
            jsCode,
            'jwplayer_options')
        json = self._parse_json(jwplayer_options, video_id, js_to_json)
        json['title'] = title

        result = self._parse_jwplayer_data(json, video_id)
        for video in result['formats']:
            video['http_headers'] = {
                'User-Agent': std_headers['User-Agent'],
                'Range': 'bytes=0-'
            }

        return result


class HKAnimeIE(HKAnimeBaseInfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?hkanime\.com/animal/(?P<id>[0-9]+x[0-9]+x[0-9]+)'
    _TEST = {
        'url': 'https://www.hkanime.com/animal/416x1x1',
        'md5': '3f081ba17d6bf6e1de3f8e72a4c63cf8',
        'info_dict': {
            'id': 'erKsLAUk2c3l5Jl',
            'ext': 'mp4',
            'title': '[\u7cb5\u8a9e] \u4e00\u62f3\u8d85\u4eba 2 - EP01 \u82f1\u96c4\u56de\u6b78',
            'thumbnail': r're:^https?://play.hkanime.com/thumbnail/.*$',
        }
    }

    def _real_extract(self, url):
        # Get video page
        path_id = self._match_id(url)
        webpage = self._download_webpage(url, path_id)

        # Get series meta data
        series_name = self._html_search_regex(
            r'mac_name=\'(.+?)\'',
            webpage,
            'series_name')
        series_info = self._html_search_regex(
            r'mac_url=unescape\(base64decode\(\'(.+?)\'\)\);',
            webpage,
            'series_info')
        episode_no = path_id.split('x')[2]
        (title, video_id) = self._get_episode_info(series_info, episode_no)

        return self._get_video_info_by_id(video_id, series_name + ' - ' + title)
