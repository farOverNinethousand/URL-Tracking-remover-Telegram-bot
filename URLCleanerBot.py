import json

import pydantic
from telegram import Update, User
from telegram.ext import CommandHandler, CallbackContext, Application, filters, MessageHandler

from URLCleaner import URLCleaner


class Config(pydantic.BaseModel):
    bot_token: str
    bot_name: str


def loadConfig() -> Config:
    with open('config.json', encoding='utf-8') as infile:
        jsondict = json.load(infile)
        return Config(**jsondict)

# TODO: Move translation int external (json) files
langDE = dict(
    command_start_bot_info="Dieser Bot entfernt Trackingparameter von URLs.\nZusätzlich werden auch MyDealz Tracking-URLs abgeändert:\nBeispiel:\nmydealz.de/share-deal-from-app/2117879\n->Wird zu:\nmydealz.de/diskussion/a-2117879\nSende einen oder mehrere Links an diesen Bot und erhalte Links ohne Tracking.\nDieser Bot speichert keinerlei Daten.\nSource code and support: TODO",
    text_cleaned_urls_fail="❌Keine Links gefunden.",
    text_cleaned_urls_success="✅Detected {numlinks:.0f} URL(s):",
    text_cleaned_urls_success_snippet_clickable_link="Klickbarer Link:\n{0}",
    text_cleaned_urls_success_snippet_applied_rules="Angewendete Regeln: {0}",
    text_cleaned_urls_success_removed_parameters="Entfernte Parameter: {0}",
    text_none="Keine",
    text_url_is_already_clean_questionmark="URL was already clean?"
)

langEN = dict(
    command_start_bot_info="This bot is removing tracking-parameters from URLs.\nExample:\nyoutu.be/YAKTL0MEK34?si=8dgziuhv57GFfgs4Y0u_\n->Gets changed to:\nyoutu.be/YAKTL0MEK34\nSend one or multiple URLs to this bot.\nThis bot does not store any user-data.\nQuellcode und Support: TODO",
    text_cleaned_urls_fail="❌Failed to find any links.",
    text_cleaned_urls_success="✅{numlinks:.0f} URL(s) gefunden:",
    text_cleaned_urls_success_snippet_clickable_link="Clickable link:\n{0}",
    text_cleaned_urls_success_snippet_applied_rules="Applied rules: {0}",
    text_cleaned_urls_success_removed_parameters="Removed parameters: {0}",
    text_none="None",
    text_url_is_already_clean_questionmark="URL war bereits clean?"
)

allLangsDict = dict(
    de=langDE,
    en=langEN
)


def translate(key: str, lang: str) -> str:
    """ Returns translated text """
    langdict = allLangsDict.get(lang, "en")
    return langdict.get(key, key)


class URLCleanerBot:
    def __init__(self):
        self.cfg = loadConfig()
        self.application = Application.builder().token(self.cfg.bot_token).read_timeout(30).write_timeout(30).build()
        self.initHandlers()
        self.urlcleaner = URLCleaner()
        # mainTranslationDir = "locales"
        # languages = ["de", "en"]
        # for language in languages:
        #     translationPath = os.path.join(mainTranslationDir, language, "LC_MESSAGES")
        #     # os.mkdir(translationPath)
        #     if not os.path.isdir(translationPath):
        #         os.makedirs(translationPath)

    def initHandlers(self):
        """ Adds all handlers to dispatcher (not error_handlers!!) """
        self.application.add_handler(CommandHandler('start', self.botDisplayMenuMain))
        self.application.add_handler(CommandHandler('help', self.botDisplayMenuMain))
        self.application.add_handler(MessageHandler(filters=filters.TEXT and (~filters.COMMAND), callback=self.botCleanURLs))

    async def botDisplayMenuMain(self, update: Update, context: CallbackContext):
        text = "<b>URLCleaner 0.2</b>"
        text += f"\n{self.translate('command_start_bot_info', update.effective_user)}"
        return await self.application.updater.bot.send_message(chat_id=update.effective_user.id, text=text, parse_mode="HTML",
                                                               disable_web_page_preview=True)

    async def botCleanURLs(self, update: Update, context: CallbackContext):
        userInput = update.message.text
        user = update.effective_user
        cleanedurls = self.urlcleaner.getCleanedURLs(userInput)
        if len(cleanedurls) == 0:
            return await self.application.updater.bot.send_message(chat_id=user.id, text=self.translate("text_cleaned_urls_fail", user), parse_mode="HTML",
                                                                   disable_web_page_preview=True)

        text = self.translate("text_cleaned_urls_success", user).format(numlinks=len(cleanedurls))

        position = 1
        for cleanedurl in cleanedurls:
            newlink = cleanedurl.parsedURL.geturl()
            if len(cleanedurls) > 1:
                text += f"\n<b>URL {position}</b>"
            text += f"\nCode:\n<pre>{newlink}</pre>"
            text += f"\n" + self.translate("text_cleaned_urls_success_snippet_clickable_link", user).format(newlink)
            appliedRulesText = ""
            removedParametersText = None
            if len(cleanedurl.appliedrules) > 0:
                index = 0
                for rule in cleanedurl.appliedrules:
                    appliedRulesText += rule.name
                    if index < len(cleanedurl.appliedrules) - 1:
                        appliedRulesText += ", "
                    index += 1
                if len(cleanedurl.removedparams) > 0:
                    removedParametersText = ", ".join(cleanedurl.removedparams)
                else:
                    removedParametersText = self.translate("text_none", user)
            else:
                appliedRulesText = self.translate("text_none", user) + " -> " + self.translate("text_url_is_already_clean_questionmark", user)
            text += "\n" + self.translate("text_cleaned_urls_success_snippet_applied_rules", user).format(appliedRulesText)
            if removedParametersText is not None:
                text += "\n" + self.translate("text_cleaned_urls_success_removed_parameters", user).format(removedParametersText)
            if position < len(cleanedurls) - 1:
                # Not the last entry -> Add separator
                text += "\n---"
            position += 1
        return await self.application.updater.bot.send_message(chat_id=update.effective_user.id, text=text, parse_mode="HTML",
                                                               disable_web_page_preview=True)

    def translate(self, key, user: User):
        lang = user.language_code
        return translate(key, lang)

    def startBot(self):
        self.application.run_polling(timeout=300, read_timeout=300, write_timeout=300, connect_timeout=300)

    def stopBot(self):
        self.application.stop()


def main():
    bkbot: URLCleanerBot = URLCleanerBot()
    bkbot.startBot()


if __name__ == '__main__':
    main()
