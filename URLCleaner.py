import json
import os.path
import random
import re
import string
from typing import List, Union
from urllib.parse import urlparse, parse_qs, urlencode, unquote

from pydantic.json import pydantic_encoder

from CleaningRule import CleaningRule


class CleanedURL:
    """ Represents a URL which will be cleaned.
     Keeps track of all changes that were made to this URL.
     """

    def __init__(self, url: str):
        self.originalurl = url
        self.cleanedurl = urlparse(url)
        self.newurl_regex = None
        self.newurl_urlparam = None
        self.newurl = None
        self.query = parse_qs(self.cleanedurl.query, keep_blank_values=True)
        self.appliedrules = []
        self.removedparams_affiliate = []
        self.removedparams_tracking = []
        self.isException = False


class CleanResult:
    """ Represents the result of a text string which was cleaned. """

    def __init__(self, text: str, cleanedtext: str, cleanedurls: List[CleanedURL]):
        self.originaltext = text
        self.cleanedtext = cleanedtext
        self.cleanedurls = cleanedurls


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

    def importCleaningRules(self, path: str) -> List[CleaningRule]:
        """ TODO: Add functionality
         Load rules from file and add them to global list of cleaning rules.
         """
        if not os.path.exists(path):
            raise Exception(f"File does not exist: {path}")
        newrules = []
        with open(path, encoding='utf-8') as infile:
            jsonobject = json.load(infile)
            if isinstance(jsonobject, list):
                # Assume this json is proprietary from this project
                for item in jsonobject:
                    rule = CleaningRule(**item)
                    newrules.append(rule)
            else:
                # Check for other sources
                providers: dict = jsonobject.get("providers")
                if providers is not None:
                    # rule json from ClearURLs addon: https://github.com/ClearURLs/Addon
                    # Docs: https://docs.clearurls.xyz/1.26.1/specs/rules/
                    """ Some rules are blacklisted since their original is buggy or is lacking features.
                     Example github.com: Original rule does not remove this parameter: notification_referrer_id, reference: https://github.com/ClearURLs/Rules/issues/114
                     """
                    blacklistedRules = ["github.com"]
                    for rulename, providermap in providers.items():
                        if rulename in blacklistedRules:
                            print(f"Skipping import of blacklisted rule: {rulename}")
                            continue
                        paramlist = providermap.get("rules")
                        # TODO: Migrate missing fields
                        completeProvider = providermap.get("completeProvider")
                        redirections = providermap.get("redirections")
                        rawRules = providermap.get("rawRules")
                        exceptions = providermap.get("exceptions")
                        referralMarketing = providermap.get("referralMarketing")
                        newrule = CleaningRule(name=rulename, description="Rule imported from 'github.com/ClearURLs/Addon'"
                                               , paramsblacklist=paramlist)
                        newrule.urlPattern = providermap["urlPattern"]
                        newrule.forceRedirection = providermap.get("forceRedirection")
                        if exceptions is not None:
                            newrule.exceptionsregexlist = exceptions
                        if referralMarketing is not None:
                            newrule.paramsblacklist_affiliate = referralMarketing
                        if redirections is not None:
                            newrule.redirectsregexlist = redirections

                        newrules.append(newrule)

                else:
                    raise Exception("Invalid import data")
        print(f"New rules loaded: {len(newrules)}")
        for rule in newrules:
            if rule not in self.cleaningrules:
                self.cleaningrules.append(rule)
        return newrules

    def saveCleaningRules(self, path: Union[str, None]):
        """
         Stores all loaded rules into json file to desired path, default as "cleaningrules.json".
         """
        if path is None:
            path = "cleaningrules.json"
        bigger_data_json = json.dumps(self.cleaningrules, default=pydantic_encoder)
        print("Writing json to file:")
        print(bigger_data_json)
        f = open(path, "w")
        f.write(bigger_data_json)

    def cleanText(self, text: str) -> CleanResult:
        cleanedurls = []
        urls = URL_REGEX.findall(text)
        for url in urls:
            try:
                cleanedurl = CleanedURL(url)
            except:
                # We are not validating those URLs before so errors during parsing may happen
                continue
            for cleaningrule in self.cleaningrules:
                if cleaningrule.enabled is False:
                    # Skip disabled rules
                    continue
                ruleApplicationStatus = self.cleanURL(cleanedurl, cleaningrule)
                if cleanedurl.isException:
                    # Rule contained an exception regex so this URL shall not be changed.
                    break
                elif ruleApplicationStatus is True and cleaningrule.stopAfterThisRule:
                    break
            cleanedurls.append(cleanedurl)
        cleanedtext = text
        for cleanedurl in cleanedurls:
            cleanedtext = cleanedtext.replace(cleanedurl.originalurl, cleanedurl.cleanedurl.geturl())
        result = CleanResult(text=text, cleanedtext=cleanedtext, cleanedurls=cleanedurls)
        return result

    def cleanURL(self, cleanedurl: CleanedURL, rule: CleaningRule) -> bool:
        """ Check for exceptions by regex. """
        if rule.urlPattern is not None:
            if re.search(rule.urlPattern, cleanedurl.originalurl) is None:
                # URL does not match pattern of this rule
                return False
        for exceptionregex in rule.exceptionsregexlist:
            if re.search(exceptionregex, cleanedurl.originalurl):
                cleanedurl.isException = True
                return True

        if len(rule.domainwhitelist) > 0:
            # Check if rule-execution is allowed by whitelist if we got a whitelist
            domain = cleanedurl.cleanedurl.hostname
            if rule.domainwhitelistIgnoreWWW:
                domain = domain.replace('www.', '')
            if domain not in rule.domainwhitelist:
                # Rule has domain-whitelist and domain of given URL is not on that whitelist so we cannot apply the rule.
                return False
        appendedRule = False
        newurl = None
        newurl_regex = None
        newurl_urlparam = None
        rewriteurlregex = rule.rewriteURLSourcePattern.search(cleanedurl.originalurl) if rule.rewriteURLSourcePattern is not None else None
        if rewriteurlregex:
            newurl = rule.rewriteURLScheme
            # if newurl is None:
            #     # Default: Use first match
            #     newurl = "<regexmatch:0>"
            matches = re.finditer(rule.rewriteURLSourcePattern, cleanedurl.originalurl)
            for match in matches:
                for index in range(0, match.lastindex + 1):
                    matchText = match.group(index)
                    newurl = newurl.replace(f"<regexmatch:{index}>", matchText)
            randomletter = random.choice(string.ascii_lowercase)
            # Execute other replacements
            newurl = newurl.replace(f"<randomchar>", randomletter)
            newurl_regex = str(rule.rewriteURLSourcePattern)
            appendedRule = True
        if len(rule.redirectsregexlist) is not None:
            for pattern_str in rule.redirectsregexlist:
                regex = re.search(pattern_str, cleanedurl.originalurl)
                if regex:
                    # Hit
                    newurl = regex.group(1)
                    newurl_regex = pattern_str
                    appendedRule = True
                    break
        if newurl is None and len(rule.redirectparameterlist) > 0:
            for urlparam in rule.redirectparameterlist:
                newurl = cleanedurl.query.get(urlparam)
                if newurl is not None:
                    newurl_urlparam = urlparam
                    break


        if newurl is not None:
            # URL-decode result
            newurl = unquote(newurl)
            cleanedurl.newurl = newurl
            cleanedurl.newurl_regex = newurl_regex
            cleanedurl.newurl_urlparam = newurl_urlparam
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
        # Collect tracking parameters which should be removed
        removeParamsTracking = []
        if rule.removeAllParameters:
            # Remove all parameters from given URL RE: https://github.com/svenjacobs/leon/issues/70
            for key in cleanedurl.query.keys():
                removeParamsTracking.append(key)
            # cleanedurl.parsedURL = cleanedurl.parsedURL._replace(query=None)
            # cleanedurl.query = None
            # appendedRule = True
        elif rule.paramswhitelist is not None:
            for key in cleanedurl.query.keys():
                if key not in rule.paramswhitelist:
                    removeParamsTracking.append(key)
            # cleanedurl.parsedURL = cleanedurl.parsedURL._replace(query=None)
            # cleanedurl.query = None
            # appendedRule = True
        elif rule.paramsblacklist is not None:
            removeParamsTracking = rule.paramsblacklist
        removedParams = []
        # Only remove affiliate related stuff if we are allowed to
        if self.removeAffiliate and len(rule.paramsblacklist_affiliate) > 0:
            removedParamsAffiliate = self.removeUrlParameters(cleanedurl, rule.paramsblacklist_affiliate)
            removedParams += removedParamsAffiliate
            cleanedurl.removedparams_affiliate += removedParamsAffiliate
        if len(removeParamsTracking) > 0:
            removedParamsTracking = self.removeUrlParameters(cleanedurl, removeParamsTracking)
            removedParams += removedParamsTracking
            cleanedurl.removedparams_tracking += removedParamsTracking
        # Replace query inside URL as we've changed the query
        if len(removedParams) > 0:
            cleanedurl.cleanedurl = cleanedurl.cleanedurl._replace(query=urlencode(cleanedurl.query, True))
            appendedRule = True

        if appendedRule:
            cleanedurl.appliedrules.append(rule)
        return appendedRule

    def removeUrlParameters(self, cleanedurl: CleanedURL, paramsToRemove):
        removedParams = []
        paramsRegex = []
        for param in paramsToRemove:
            if cleanedurl.query.pop(param, None) is not None:
                removedParams.append(param)
            else:
                paramsRegex.append(param)
        for paramRegex in paramsRegex:
            # Remove parameters via regular expression
            for paramkey in list(cleanedurl.query.keys()):
                try:
                    if re.search(paramRegex, paramkey) is not None:
                        cleanedurl.query.pop(paramkey)
                        removedParams.append(paramkey)
                        break
                except:
                    print(f"Invalid regular expression added by user: {paramRegex}")
                    pass
        return removedParams


def getDefaultCleaningRules() -> List[CleaningRule]:
    cleaningrules = [CleaningRule(name="Google's Urchin Tracking Module",
                                  paramsblacklist=["_ga", "utm_id", "utm_source", "utm_medium", "utm_term", "utm_campaign", "utm_content", "utm_name", "utm_cid",
                                                   "utm_reader", "utm_viz_id",
                                                   "utm_pubreferrer", "utm_swu", "_ga", "gclsrc", "dclid", "adposition", "campaignid", "adgroupid", "feeditemid",
                                                   "targetid"], stopAfterThisRule=False),
                     CleaningRule(name="Google Click Identifier", paramsblacklist=["gclid"]),
                     CleaningRule(name="Adobe Omniture SiteCatalyst", paramsblacklist=["IC_ID"]),
                     CleaningRule(name="Adobe misc", paramsblacklist=["s_cid", "s_kwcid"]),
                     CleaningRule(name="Hubspot",
                                  paramsblacklist=["_hs_enc", "_hs_mi", "hsa_cam", "hsa_grp", "hsa_mt", "hsa_src", "hsa_ad", "hsa_acc", "hsa_net", "hsa_cam", "hsa_grp",
                                                   "hsa_mt", "hsa_src", "hsa_ad", "hsa_acc", "hsa_net", "hsa_kw", "hsa_tgt", "hsa_ver"]),
                     CleaningRule(name="Marketo", paramsblacklist=["mkt_tok"]),
                     # https://mailchimp.com/developer/marketing/docs/e-commerce/
                     CleaningRule(name="MailChimp", paramsblacklist=["mc_cid", "mc_eid"]),
                     CleaningRule(name="SimpleReach", paramsblacklist=["sr_share"]),
                     CleaningRule(name="Vero", paramsblacklist=["vero_conv", "vero_id"]),
                     CleaningRule(name="Spotify/YouTube Share Identifier", paramsblacklist=["si"]),
                     CleaningRule(name="Facebook Click Identifier", paramsblacklist=["fbclid"]),
                     CleaningRule(name="Instagram Share Identifier", paramsblacklist=["igsh", "igshid", "srcid"]),
                     CleaningRule(name="Some other Google Click thing", paramsblacklist=["ocid"]),
                     CleaningRule(name="Alibaba-family 'super position model' tracker",
                                  description="Requested by a user here: https://github.com/newhouse/url-tracking-stripper/issues/38",
                                  paramsblacklist=["spm"]),
                     CleaningRule(name="Piwik", paramsblacklist=["pk_campaign", "pk_kwd", "pk_keyword", "piwik_campaign", "piwik_kwd", "piwik_keyword"]),
                     CleaningRule(name="Matomo (old name: Piwik)",
                                  paramsblacklist=["mtm_campaign", "mtm_keyword", "mtm_source", "mtm_medium", "mtm_content", "mtm_cid", "mtm_group", "mtm_placement",
                                                   "matomo_campaign", "matomo_keyword", "matomo_source", "matomo_medium", "matomo_content", "matomo_cid", "matomo_group",
                                                   "matomo_placement"]),
                     CleaningRule(name="Microsoft", paramsblacklist=["msclkid"]),
                     CleaningRule(name="Yandex", paramsblacklist=["yclid", "_openstat"]),
                     CleaningRule(name="Salesforce Activity-ID", paramsblacklist=["sfmc_activityid"]),
                     CleaningRule(name="Ebay remove all parameters except for whitelist",
                                  description="Source of supported domains: https://pages.ebay.com/securitycenter/security_researchers_eligible_domains.html",
                                  domainwhitelist=["ebay.com", "ebay.co.uk", "ebay.com.au", "ebay.de", "ebay.ca", "ebay.fr", "ebay.it", "ebay.es", "ebay.at", "ebay.ch",
                                                   "ebay.com.hk", "ebay.com.sg", "ebay.com.my", "ebay.in", "ebay.ph", "ebay.ie", "ebay.pl", "ebay.be", "ebay.nl",
                                                   "ebay.cn", "ebay.com.tw", "ebay.co.jp", "ebaythailand.co.th", "cpass.ebay.com"],
                                  paramswhitelist=["_nkw", "s", "q", "catid"]),
                     # Source: https://gist.github.com/AminulBD/8c347539ecd49a8ab0b24544dd2ebab1
                     CleaningRule(name="Amazon remove all parameters test",
                                  description="Removes all parameters from any amazon URLs since usually people are sending roduct URLs where only the product-ID matters and that is part of the path and not a parameter.",
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
                     CleaningRule(name="Google Play Store",
                                  description="Idea from: https://github.com/svenjacobs/leon/issues/308",
                                  domainwhitelist=["store.google.com"], paramsblacklist=["selections"]),
                     # https://github.com/svenjacobs/leon/issues/358
                     CleaningRule(name="MyDealz Tracking Redirect Remover",
                                  description="Changes such links: 'mydealz.de/share-deal-from-app/2117879' to such links: 'mydealz.de/deals/a-2117879'",
                                  rewriteURLSourcePattern=r"(?i)https?://([^/]+)/share-deal-from-app/(\d+)",
                                  rewriteURLScheme="https://<regexmatch:1>/deals/<randomchar>-<regexmatch:2>", testurls=["https://mydealz.de/share-deal-from-app/2117879"]),
                     CleaningRule(name="github.com",
                                  description="Improved ClearURLs rule based on: https://github.com/ClearURLs/Rules/issues/114",
                                  domainwhitelist=["github.com"], paramsblacklist=["email_token", "email_source", "notification_referrer_id"],
                                  testurls=["https://github.com/mmikeww/AHK-v2-script-converter/pull/200?notification_referrer_id=NT_kwDOBQCiV7QxMTEzMTY3ODgwMjo4MzkyNzYzOQ#event-13195027062"]
                                  ),
                     CleaningRule(name="tvnet.lv",
                                  description="Idea from: https://github.com/ClearURLs/Rules/issues/112",
                                  domainwhitelist=["tvnet.lv"], paramsblacklist=["pnespid"],
                                  testurls=["https://www.tvnet.lv/7966163/lusis-komente-kas-maskavas-ielai-kopigs-ar-krievu-karakugi?pnespid=WLAg5FBL9X9IyE6J7pPWSE1HvEk5nbwtul4QB.1dasnK8IUATWMh.omiCHhAMsUHGhQMTwHYlg"]),
                     CleaningRule(name="komoot.com",
                                  description="Idea from: https://github.com/ClearURLs/Rules/issues/111",
                                  domainwhitelist=["komoot.com"], paramsblacklist=["share_token", "ref"],
                                  testurls=["https://www.komoot.com/tour/1543654902?share_token=aVODnLAvDj1M0BWJrXN2zouh9HFGB6fAMGY4Xl5KsloLpTcrtp&ref=wtd"]),
                     CleaningRule(name="1fichier.com",
                                  description="Idea from: https://github.com/ClearURLs/Rules/issues/104",
                                  domainwhitelist=["1fichier.com"], paramsblacklist_affiliate=["af"],
                                  testurls=["https://1fichier.com/?j22232ehs40pki4x93wg&af=3787696"]),
                     CleaningRule(name="douyu.com",
                                  description="Idea from: https://github.com/ClearURLs/Rules/issues/98",
                                  domainwhitelist=["douyu.com"], paramsblacklist=["dyshid", "dyshci"],
                                  testurls=["https://www.douyu.com/11682346?dyshid=0-&dyshci=1"])
                     ]
    return cleaningrules


def main():
    cleaner = URLCleaner()
    cleaner.importCleaningRules("cleaningrules.json")
    clearurlsaddon_rules_file = "data.minify.json"
    if os.path.exists(clearurlsaddon_rules_file):
        print("Test, importing rules from https://github.com/ClearURLs/Addon")
        cleaner.importCleaningRules(clearurlsaddon_rules_file)
    cleaner.saveCleaningRules("cleaningrules_save_test.json")


if __name__ == '__main__':
    main()
