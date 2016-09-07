from config import Config
from lxml import html
import requests

# import json

RIETVELD_AUTH_URL = Config.RIETVELD_URL + 'xsrf_token'
RIETVELD_MY_ISSUES_URL = Config.RIETVELD_URL + 'user/' + Config.RIETVELD_USER
RIETVELD_API_ISSUE_URL = Config.RIETVELD_URL + 'api/{}'
RIETVELD_ISSUE_XPATH = '//tr[@name="issue"]/ td[{}] / div / a / text()[following::*[contains(text(),"Issues Closed Recently")]]'

RIETVELD_ISSUE_URL = Config.RIETVELD_URL + '{}'


def all_issues():
    page = requests.get(RIETVELD_MY_ISSUES_URL)
    tree = html.fromstring(page.content)
    # print(page.content)

    issue_ids = tree.xpath(RIETVELD_ISSUE_XPATH.format(3))
    issue_titles = tree.xpath(RIETVELD_ISSUE_XPATH.format(4))

    # issues = []
    #
    # for i in issue_ids:
    #     ipage = requests.get(RIETVELD_API_ISSUE_URL.format(i))
    #     print(ipage.content.decode())
    #     issues.append(json.loads(ipage.content.decode()))

    return map(int, issue_ids), issue_titles
    # return issues
