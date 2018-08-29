from lxml import html
from lxml.etree import _ElementStringResult, _ElementUnicodeResult
from searx.utils import html_to_text
from searx.url_utils import unquote, urlencode, urljoin, urlparse
from searx.engines.licensing import CreativeCommons

search_url = None
url_xpath = None
content_xpath = None
title_xpath = None
img_src_xpath = None
thumbnail_src_xpath = None
paging = False
suggestion_xpath = ''
results_xpath = ''

# parameters for engines with paging support
#
# number of results on each page
# (only needed if the site requires not a page number, but an offset)
page_size = 1
# number of the first page (usually 0 or 1)
first_page_num = 1


'''
if xpath_results is list, extract the text from each result and concat the list
if xpath_results is a xml element, extract all the text node from it
   ( text_content() method from lxml )
if xpath_results is a string element, then it's already done
'''


def extract_text(xpath_results):
    if type(xpath_results) == list:
        # it's list of result : concat everything using recursive call
        result = ''
        for e in xpath_results:
            result = result + extract_text(e)
        return result.strip()
    elif type(xpath_results) in [_ElementStringResult, _ElementUnicodeResult]:
        # it's a string
        return ''.join(xpath_results)
    else:
        # it's a element
        text = html.tostring(xpath_results, encoding='unicode', method='text', with_tail=False)
        text = text.strip().replace('\n', ' ')
        return ' '.join(text.split())


def extract_url(xpath_results, search_url):
    if xpath_results == []:
        raise Exception('Empty url resultset')
    url = extract_text(xpath_results)

    if url.startswith('//'):
        # add http or https to this kind of url //example.com/
        parsed_search_url = urlparse(search_url)
        url = u'{0}:{1}'.format(parsed_search_url.scheme or 'http', url)
    elif url.startswith('/'):
        # fix relative url to the search engine
        url = urljoin(search_url, url)

    # normalize url
    url = normalize_url(url)

    return url


def normalize_url(url):
    parsed_url = urlparse(url)

    # add a / at this end of the url if there is no path
    if not parsed_url.netloc:
        raise Exception('Cannot parse url')
    if not parsed_url.path:
        url += '/'

    # FIXME : hack for yahoo
    if parsed_url.hostname == 'search.yahoo.com'\
       and parsed_url.path.startswith('/r'):
        p = parsed_url.path
        mark = p.find('/**')
        if mark != -1:
            return unquote(p[mark + 3:]).decode('utf-8')

    return url


def request(query, params):
    query = urlencode({'q': query})[2:]

    fp = {'query': query}
    if paging and search_url.find('{pageno}') >= 0:
        fp['pageno'] = (params['pageno'] - 1) * page_size + first_page_num

    params['url'] = search_url.format(**fp)
    params['query'] = query

    return params


def response(resp):
    results = []
    dom = html.fromstring(resp.text)
    if results_xpath:
        for result in dom.xpath(results_xpath):
            url = extract_url(result.xpath(url_xpath), search_url)
            title = extract_text(result.xpath(title_xpath))
            content = extract_text(result.xpath(content_xpath))
            thumbnail_src = extract_text(result.xpath(thumbnail_src_xpath))
            img_src = extract_text(result.xpath(img_src_xpath))
            results.append({
                'url': url,
                'title': title,
                'content': content,
                'thumbnail_src': thumbnail_src,
                'img_src': img_src,
                'license': CreativeCommons().zero,
                'template': 'images.html',
                })
    else:
        for url, title, content, thumbnail_src, img_src in zip(
            (extract_url(x, search_url) for
             x in dom.xpath(url_xpath)),
            map(extract_text, dom.xpath(title_xpath)),
            map(extract_text, dom.xpath(content_xpath)),
            map(extract_text, dom.xpath(thumbnail_src_xpath)),
            map(extract_text, dom.xpath(img_src_xpath))
        ):
            results.append({
                'url': url,
                'title': title,
                'content': content,
                'thumbnail_src': thumbnail_src,
                'img_src': img_src,
                'template': 'images.html',
                })

    if not suggestion_xpath:
        return results
    for suggestion in dom.xpath(suggestion_xpath):
        results.append({'suggestion': extract_text(suggestion)})
    return results
