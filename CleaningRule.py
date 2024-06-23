import re
from typing import Union, List, Optional

from pydantic import BaseModel, root_validator, validator


class CleaningRule(BaseModel):
    """
    Arguments:

    name: Name of the rule
    description of rule: Can be used to provide examples on what this does but also to explain why it is done in a certain way.
    urlPattern: Pattern of the URL if pattern matching is preferred.
    paramsblacklist: List of parameters to be removed from URL
    paramsblacklist_affiliate: List of affiliate related parameters to be removed from URL
    removeAllParameters: If set to true, all parameters will be removed from the source-URL
    domainwhitelist: Whitelist of domains this rule should act upon. None = rule will be applied to all URLs which match the rules' pattern.
    stopAfterThisRule: Set this to True if this rule is allowed to break the URL-cleaning-loop if applied successfully.
    domainwhitelistIgnoreWWW: Ignore 'www.' in whitelist domain matching

    exceptionsregexlist: List of regular expressions for URL patterns where
    rewriteURLSourcePattern: Regular expression to be used as source for building a new URL e.g. https://mydealz.de/share-deal-from-app/(\d+)
    rewriteURLScheme: Scheme to be used to URL-rewriting e.g. https://mydealz.de/deals/x-<regexmatch:1>
    forceRedirection: Not used at this moment, stolen/imported from ClearURLs project, see: https://docs.clearurls.xyz/1.26.1/specs/rules/#forceredirection
    redirectsregexlist: List of regexes to find new URL inside existing URL. First match will be used.
    redirectparameterlist: List of possible URL parameters to find new URL. First match will be used.
    testurls: URLs for testing this rule


    Returns None.
     """
    name: str
    description: Optional[str]
    enabled: Optional[bool] = True
    urlPattern: Optional[str]
    paramsblacklist: Optional[List[str]]
    paramsblacklist_affiliate: Optional[List[str]]
    paramswhitelist: Optional[List[str]]
    domainwhitelist: Optional[List[str]] = []
    domainwhitelistIgnoreWWW: Optional[bool] = True
    exceptionsregexlist: Optional[List[str]] = []
    redirectsregexlist: Optional[List[str]] = []
    redirectparameterlist: Optional[List[str]] = []
    removeAllParameters: Optional[bool] = False
    stopAfterThisRule: Optional[bool] = True
    rewriteURLSourcePattern: Optional[Union[str, re.Pattern, None]]
    rewriteURLScheme: Optional[str]
    forceRedirection: Optional[bool]
    testurls: Optional[List[str]]

    @validator("domainwhitelist")
    def verify_domainwhitelist(cls, value):
        if value is None:
            return []
        else:
            return value

    @validator("rewriteURLSourcePattern")
    def verify_rewriteURLSourcePattern(cls, value):
        if value is None:
            return None
        elif isinstance(value, re.Pattern):
            return value
        else:
            value = re.compile(value)
            return value

    @root_validator()
    def verify_rest(cls, values):
        """
         TODO: Add more checks e.g. check for rule with blacklist and whitelist params entries
         """
        paramsblacklist = values.get('paramsblacklist')
        removeAllParameters = values.get('removeAllParameters')
        paramswhitelist = values.get('paramswhitelist')
        rewriteURLSourcePattern = values.get('rewriteURLSourcePattern')
        rewriteURLScheme = values.get('rewriteURLScheme')
        urlPattern = values.get('urlPattern')
        redirectsregexlist = values.get('redirectsregexlist')
        if paramsblacklist is None and removeAllParameters is False and paramswhitelist is None and rewriteURLSourcePattern is None and rewriteURLScheme is None and urlPattern is None and redirectsregexlist is None:
            raise ValueError(f"Minumum parameters are not given | {paramsblacklist=} {removeAllParameters=} {rewriteURLSourcePattern=} {rewriteURLScheme=}")
        elif rewriteURLSourcePattern is None and rewriteURLScheme is not None:
            raise ValueError(f"{rewriteURLSourcePattern=} while rewriteURLScheme is not None")
        elif rewriteURLSourcePattern is not None and rewriteURLScheme is None:
            raise ValueError(f"{rewriteURLSourcePattern=} is not None while {rewriteURLScheme=} is None")
        return values

    # def stopAfterThisRule(self) -> bool:
    #     """ If this returns True and the rule was executed successfully on a URL, no further rules need to be processed. """
    #     if len(self.domainwhitelist) > 0:
    #         return True
    #     elif self.removeAllParameters:
    #         return True
    #     else:
    #         return self.forceStopAfterThisRule
