import re
from typing import Union, List, Optional

from pydantic import BaseModel, root_validator, validator


class CleaningRule(BaseModel):
    """
    Arguments:

    name: Name of the rule
    paramsblacklist: List of parameters to be removed from URL
    removeAllParameters: If set to true, all parameters will be removed from the source-URL
    domainwhitelist: Whitelist of domains this rule should act upon. None = rule will be applied to all URLs.
    stopAfterThisRule: Set this to True if this rule is allowed to break the URL-cleaning-loop if applied successfully.
    domainwhitelistIgnoreWWW: Ignore 'www.' in whitelist domain matching

    rewriteURLSourcePattern: Regular expression to be used as source for building a new URL e.g. https://mydealz.de/share-deal-from-app/(\d+)
    rewriteURLScheme: Scheme to be used to URL-rewriting e.g. https://mydealz.de/deals/x-<regexmatch:1>
    testurls: URLs for testing this rule


    Returns None.
     """
    name: str
    paramsblacklist: Optional[List[str]]
    paramswhitelist: Optional[List[str]]
    domainwhitelist: Optional[List[str]] = []
    domainwhitelistIgnoreWWW: Optional[bool] = True
    removeAllParameters: Optional[bool] = False
    forceStopAfterThisRule: Optional[bool] = False
    rewriteURLSourcePattern: Optional[Union[str, re.Pattern, None]]
    rewriteURLScheme: Optional[str]
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
        paramsblacklist = values.get('paramsblacklist')
        removeAllParameters = values.get('removeAllParameters')
        paramswhitelist = values.get('paramswhitelist')
        rewriteURLSourcePattern = values.get('rewriteURLSourcePattern')
        rewriteURLScheme = values.get('rewriteURLScheme')
        if paramsblacklist is None and removeAllParameters is False and paramswhitelist is None and rewriteURLSourcePattern is None and rewriteURLScheme is None:
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
