import json
import random
import re
import string
from typing import List
from urllib.parse import urlparse, parse_qs, urlencode

from pydantic.json import pydantic_encoder

from CleaningRule import CleaningRule


class CleanedURL:
    """ Represents a URL which will be cleaned.
     Keeps track of all changes that were made to this URL.
     """

    def __init__(self, url: str):
        self.originalurl = url
        self.cleanedurl = urlparse(url)
        self.query = parse_qs(self.cleanedurl.query, keep_blank_values=True)
        self.appliedrules = []
        self.removedparams_affiliate = []
        self.removedparams_tracking = []


# Very cheap regex to find URLs inside a text
URL_REGEX = re.compile(r'(?i)(https?://\S+)')


class URLCleaner:
    def __init__(self):
        """ CleaningRules are based on infos I stole from various other projects:
         https://github.com/newhouse/url-tracking-stripper/blob/master/assets/js/trackers.js

         https://github.com/inframanufaktur/clean-urls/blob/main/data/params.js

         https://github.com/doggy8088/TrackingTokenStripper/blob/master/README.md

         https://github.com/svenjacobs/leon/blob/main/core-domain/src/test/kotlin/com/svenjacobs/app/leon/core/domain/sanitizer/amazon/AmazonProductSanitizerTest.kt#L27

         TODO: Add tests similar to this: https://github.com/inframanufaktur/clean-urls/blob/main/__tests__/removeTrackingParamsFromLinks.spec.js

         """
        self.cleaningrules = getDefaultCleaningRules()
        self.removeTracking = True
        # TODO: Add functionality
        self.removeAffiliate = False

    def loadCleaningRules(self, path: str):
        """ TODO: Add functionality
         Load rules from file and add them to global list of cleaning rules.
         """
        pass

    def getCleanedURLs(self, text: str) -> List[CleanedURL]:
        cleanedurls = []
        urls = URL_REGEX.findall(text)
        for url in urls:
            try:
                cleanedurl = CleanedURL(url)
            except:
                # We are not validating those URLs before so errors during parsing may happen
                continue
            for cleaningrule in self.cleaningrules:
                ruleApplicationStatus = self.cleanURL(cleanedurl, cleaningrule)
                if ruleApplicationStatus is True and cleaningrule.forceStopAfterThisRule:
                    break
            cleanedurls.append(cleanedurl)
        return cleanedurls

    def cleanURL(self, cleanedurl: CleanedURL, rule: CleaningRule) -> bool:
        if len(rule.domainwhitelist) > 0:
            # Check if rulee-xecution is allowed by whitelist
            domain = cleanedurl.cleanedurl.hostname
            if rule.domainwhitelistIgnoreWWW:
                domain = domain.replace('www.', '')
            if domain not in rule.domainwhitelist:
                # Rule has domain-whitelist and domain of given URL is not on that whitelist so we cannot apply the rule.
                return False
        appendedRule = False
        regex = rule.rewriteURLSourcePattern.search(cleanedurl.originalurl) if rule.rewriteURLSourcePattern is not None else None
        if regex:
            newurl = rule.rewriteURLScheme
            matches = re.finditer(rule.rewriteURLSourcePattern, cleanedurl.originalurl)
            for match in matches:
                for index in range(0, match.lastindex + 1):
                    matchText = match.group(index)
                    newurl = newurl.replace(f"<regexmatch:{index}>", matchText)
            randomletter = random.choice(string.ascii_lowercase)
            # Execute other replacements
            newurl = newurl.replace(f"<randomchar>", randomletter)
            if newurl != cleanedurl.originalurl:
                try:
                    cleanedurl.cleanedurl = urlparse(newurl)
                except:
                    # This means tat whoever created that rule f*cked up
                    print(f"Warning: Rule '{rule.name}' would result in invalid URL -> {newurl}")
            else:
                # Rule created the same URL that put in -> Rule doesn't make any sense
                # TODO: Use logging vs print statment
                print(f"Possibly wrongly designed rule: '{rule.name}' returns unmodified URL for input {cleanedurl.originalurl}")
            appendedRule = True
        # Collect parameters which should be removed
        removeParams = []
        if rule.removeAllParameters:
            # Remove all parameters from given URL RE: https://github.com/svenjacobs/leon/issues/70
            for key in cleanedurl.query.keys():
                removeParams.append(key)
            # cleanedurl.parsedURL = cleanedurl.parsedURL._replace(query=None)
            # cleanedurl.query = None
            # appendedRule = True
        elif rule.paramswhitelist is not None:
            for key in cleanedurl.query.keys():
                if key not in rule.paramswhitelist:
                    removeParams.append(key)
            # cleanedurl.parsedURL = cleanedurl.parsedURL._replace(query=None)
            # cleanedurl.query = None
            # appendedRule = True
        elif rule.paramsblacklist is not None:
            # Remove parameters we don't want
            for removeparam in rule.paramsblacklist:
                if cleanedurl.query.pop(removeparam, None) is not None:
                    removeParams.append(removeparam)
        if len(removeParams) > 0:
            for removeParam in removeParams:
                cleanedurl.query.pop(removeParam)
                cleanedurl.removedparams_tracking.append(removeParam)
            # Replace query inside URL as we've changed the query
            cleanedurl.cleanedurl = cleanedurl.cleanedurl._replace(query=urlencode(cleanedurl.query, True))
            appendedRule = True

        if appendedRule:
            cleanedurl.appliedrules.append(rule)
        return appendedRule


def getDefaultCleaningRules() -> List[CleaningRule]:
    cleaningrules = [CleaningRule(name="Google's Urchin Tracking Module",
                                  paramsblacklist=["_ga", "utm_id", "utm_source", "utm_medium", "utm_term", "utm_campaign", "utm_content", "utm_name", "utm_cid",
                                                   "utm_reader", "utm_viz_id",
                                                   "utm_pubreferrer", "utm_swu", "_ga", "gclsrc", "dclid", "adposition", "campaignid", "adgroupid", "feeditemid",
                                                   "targetid"]),
                     CleaningRule(name="Google Click Identifier", paramsblacklist=["gclid"]),
                     CleaningRule(name="Adobe Omniture SiteCatalyst", paramsblacklist=["IC_ID"]),
                     CleaningRule(name="Adobe misc", paramsblacklist=["s_cid", "s_kwcid"]),
                     CleaningRule(name="Hubspot",
                                  paramsblacklist=["_hs_enc", "_hs_mi", "hsa_cam", "hsa_grp", "hsa_mt", "hsa_src", "hsa_ad", "hsa_acc", "hsa_net", "hsa_cam", "hsa_grp",
                                                   "hsa_mt", "hsa_src", "hsa_ad", "hsa_acc", "hsa_net", "hsa_kw", "hsa_tgt", "hsa_ver"]),
                     CleaningRule(name="Marketo", paramsblacklist=["mkt_tok"]),
                     # https://developer.mailchimp.com/documentation/mailchimp/guides/getting-started-with-ecommerce/
                     CleaningRule(name="MailChimp", paramsblacklist=["mc_cid", "mc_eid"]),
                     # http://www.about-digitalanalytics.com/comscore-digital-analytix-url-campaign-generator
                     CleaningRule(name="comScore Digital Analytix?", paramsblacklist=["ns_source", "ns_mchannel", "ns_campaign", "ns_linkname", "ns_fee"]),
                     CleaningRule(name="SimpleReach", paramsblacklist=["sr_share"]),
                     CleaningRule(name="Vero", paramsblacklist=["vero_conv", "vero_id"]),
                     CleaningRule(name="Spotify/YouTube Share Identifier", paramsblacklist=["si"]),
                     CleaningRule(name="Facebook Click Identifier", paramsblacklist=["fbclid"]),
                     CleaningRule(name="Instagram Share Identifier", paramsblacklist=["igsh", "igshid", "srcid"]),
                     CleaningRule(name="Some other Google Click thing", paramsblacklist=["ocid"]),
                     # https://github.com/newhouse/url-tracking-stripper/issues/38
                     CleaningRule(name="Alibaba-family 'super position model' tracker", paramsblacklist=["spm"]),
                     CleaningRule(name="Piwik", paramsblacklist=["pk_campaign", "pk_kwd", "pk_keyword", "piwik_campaign", "piwik_kwd", "piwik_keyword"]),
                     CleaningRule(name="Matomo (old name: Piwik)",
                                  paramsblacklist=["mtm_campaign", "mtm_keyword", "mtm_source", "mtm_medium", "mtm_content", "mtm_cid", "mtm_group", "mtm_placement",
                                                   "matomo_campaign", "matomo_keyword", "matomo_source", "matomo_medium", "matomo_content", "matomo_cid", "matomo_group",
                                                   "matomo_placement"]),
                     CleaningRule(name="Microsoft", paramsblacklist=["msclkid"]),
                     CleaningRule(name="Yandex", paramsblacklist=["yclid", "_openstat"]),
                     CleaningRule(name="Salesforce Activity-ID", paramsblacklist=["sfmc_activityid"]),
                     # Source: https://pages.ebay.com/securitycenter/security_researchers_eligible_domains.html
                     CleaningRule(name="Ebay remove all parameters except for whitelist",
                                  domainwhitelist=["ebay.com", "ebay.co.uk", "ebay.com.au", "ebay.de", "ebay.ca", "ebay.fr", "ebay.it", "ebay.es", "ebay.at", "ebay.ch",
                                                   "ebay.com.hk", "ebay.com.sg", "ebay.com.my", "ebay.in", "ebay.ph", "ebay.ie", "ebay.pl", "ebay.be", "ebay.nl",
                                                   "ebay.cn", "ebay.com.tw", "ebay.co.jp", "ebaythailand.co.th", "cpass.ebay.com"],
                                  paramswhitelist=["_nkw", "s", "q", "catid"]),
                     # Source: https://gist.github.com/AminulBD/8c347539ecd49a8ab0b24544dd2ebab1
                     CleaningRule(name="Amazon remove all parameters test",
                                  domainwhitelist=["amazon.com", "amazon.co.uk", "amazon.ca", "amazon.de", "amazon.es""amazon.fr", "amazon.it", "amazon.co.jp",
                                                   "amazon.in", "amazon.cn", "amazon.com.sg", "amazon.com.mx", "amazon.ae", "amazon.com.br", "amazon.nl", "amazon.com.au",
                                                   "amazon.com.tr", "amazon.sa", "amazon.se", "amazon.pl"], removeAllParameters=True),
                     CleaningRule(name="fastcompany.com remove all parameters test",
                                  domainwhitelist=["fastcompany.com"], removeAllParameters=True),
                     CleaningRule(name="flipkart.com remove all parameters test",
                                  domainwhitelist=["flipkart.com"], removeAllParameters=True),
                     CleaningRule(name="lazada.com.my", domainwhitelist=["lazada.com.my"], removeAllParameters=True),
                     CleaningRule(name="pearl.de", domainwhitelist=["pearl.de"], removeAllParameters=True),
                     CleaningRule(name="shopee.com.my", domainwhitelist=["shopee.com.my"], removeAllParameters=True),
                     CleaningRule(name="spiegel.de", domainwhitelist=["spiegel.de"], removeAllParameters=True),
                     CleaningRule(name="theguardian.com", domainwhitelist=["theguardian.com"], removeAllParameters=True),
                     CleaningRule(name="threads.net", domainwhitelist=["threads.net"], removeAllParameters=True),
                     CleaningRule(name="tiktok.com", domainwhitelist=["tiktok.com"], removeAllParameters=True),
                     CleaningRule(name="Twitter/X", domainwhitelist=["twitter.com", "x.com"], removeAllParameters=True),
                     # Idea from: https://github.com/svenjacobs/leon/issues/308
                     # TODO: Add more domains
                     CleaningRule(name="Google Play Store", domainwhitelist=["store.google.com"], paramsblacklist=["selections"]),
                     # https://github.com/svenjacobs/leon/issues/358
                     CleaningRule(name="MyDealz Tracking Redirect Remover", rewriteURLSourcePattern=r"(?i)https?://([^/]+)/share-deal-from-app/(\d+)",
                                  rewriteURLScheme="https://<regexmatch:1>/deals/<randomchar>-<regexmatch:2>")]
    return cleaningrules


def main():
    cleaningrules = getDefaultCleaningRules()
    """ 
     Save as json. This is just a test to demonstrate what is possible and that custom rules could easily be added and loaded via json file.
     """
    bigger_data_json = json.dumps(cleaningrules, default=pydantic_encoder)
    print("Writing json to file:")
    print(bigger_data_json)
    f = open("cleaningrules.json", "w")
    f.write(bigger_data_json)
    f.close()


if __name__ == '__main__':
    main()
