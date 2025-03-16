import os
import wx
import requests
import urllib.parse
import config
import gui
import globalPluginHandler
import addonHandler
from scriptHandler import script
from gui.settingsDialogs import SettingsPanel
from gui import NVDASettingsDialog, guiHelper
import api

# Initialize translation
addonHandler.initTranslation()

# Configuration section for AI Translator
ROLE_SECTION = "AITranslater"
CONFSPEC = {
    "translateTo": "string(default=German Germany)",
    "model": "integer(default=0)"
}
config.conf.spec[ROLE_SECTION] = CONFSPEC

# API Keys from environment variables
API_LLAMA = os.getenv("API_LLAMA", "default_llama_api_key")
API_GEMINI = os.getenv("API_GEMINI", "default_gemini_api_key")


def translate(text):
    """Handles translation using different AI models."""
    prompt = (
        f"translate: {text}\n"
        f"to {config.conf[ROLE_SECTION]['translateTo']}\n"
        "Give me the translated text only."
    )

    model = config.conf[ROLE_SECTION]["model"]

    try:
        if model == 0:  # GPT-4o Mini
            return translate_gpt4o(prompt)

        elif model == 1:  # Llama 3.1
            return translate_llama(prompt)

        elif model == 2:  # Gemini
            return translate_gemini(prompt)

        else:
            return "Error: Invalid model selection"

    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"


def translate_gpt4o(prompt):
    url = (
        "https://darkness.ashlynn.workers.dev/chat/?"
        "model=gpt-4o-mini&prompt=" + urllib.parse.quote(prompt)
    )
    response = requests.get(url)
    if response.status_code == 200:
        response_json = response.json()
        return response_json.get("response", "Error: No response")
    else:
        return f"Error: API returned status code {response.status_code}"


def translate_llama(prompt):
    headers = {
        'Authorization': f'Bearer {API_LLAMA}',
        'Content-Type': 'application/json',
    }
    data = {
        "model": "llama3.1-405b",
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(
        "https://api.llama-api.com/chat/completions",
        headers=headers,
        json=data
    )
    if response.status_code == 200:
        response_json = response.json()
        return response_json.get("choices", [{}])[0].get(
            "message", {}).get("content", "Error: No response")
    else:
        return f"Error: API returned status code {response.status_code}"


def translate_gemini(prompt):
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-1.5-flash-latest:generateContent?key=" + API_GEMINI
    )
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        response_json = response.json()
        return response_json.get("candidates", [{}])[0].get(
            "content", {}).get("parts", [{}])[0].get("text",
                                                     "Error: No response")
    else:
        return f"Error: API returned status code {response.status_code}"


class ResultWindow(wx.Dialog):
    """Displays the translation result in a new window."""

    def __init__(self, text, title):
        super().__init__(gui.mainFrame, title=title)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.outputCtrl = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY
        )
        self.outputCtrl.Bind(wx.EVT_KEY_DOWN, self.onOutputKeyDown)
        sizer.Add(self.outputCtrl, proportion=1, flag=wx.EXPAND)
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.outputCtrl.SetValue(text)
        self.outputCtrl.SetFocus()
        self.Raise()
        self.Show()

    def onOutputKeyDown(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        event.Skip()


class AITranslaterSettingsPanel(SettingsPanel):
    """Settings panel for configuring the AI Translator."""

    title = ("AI Translator")

    def makeSettings(self, settingsSizer):
        sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

        self.model_label = sHelper.addItem(wx.StaticText(self, label=(
            "Model")))
        self.model_choice = sHelper.addItem(wx.Choice(self))
        self.model_choice.Set(["ChatGPT", "Llama", "Gemini"])

        self.language_label = sHelper.addItem(
            wx.StaticText(self, label=("Translate to"))
        )
        self.language_choice = sHelper.addItem(wx.Choice(self))

        languages = [
            "English", "Spanish", "French", "Portuguese",
            "German", "Arabic", "Chinese", "Japanese", "Korean"
        ]
        languages.sort()
        self.language_choice.Set(languages)

        self.model_choice.SetSelection(config.conf[ROLE_SECTION]["model"])
        self.language_choice.SetStringSelection(
            config.conf[ROLE_SECTION]["translateTo"]
        )

    def postInit(self):
        self.model_choice.SetFocus()

    def onSave(self):
        config.conf[ROLE_SECTION]["model"] = self.model_choice.Selection
        config.conf[ROLE_SECTION]["translateTo"] = (
            self.language_choice.StringSelection
        )


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """Registers global hotkeys for translation."""

    scriptCategory = ("AI Translator")
    NVDASettingsDialog.categoryClasses.append(AITranslaterSettingsPanel)

    @script(gesture="kb:NVDA+alt+t")
    def script_textInput(self, gesture):
        """Open translation window."""
        self.InputText()

    @script(gesture="kb:NVDA+alt+c")
    def script_translateClipboard(self, gesture):
        """Translate clipboard text."""
        try:
            result = translate(api.getClipData())
        except Exception as e:
            result = (f"Error: {str(e)}")
        ResultWindow(result, ("Translation Result"))

    def terminate(self):
        NVDASettingsDialog.categoryClasses.remove(AITranslaterSettingsPanel)

    def InputText(self):
        """Handle input text from the user."""
        dialog = wx.TextEntryDialog(None,
                                    "Enter the text to translate:",
                                    "Input Text")
        if dialog.ShowModal() == wx.ID_OK:
            input_text = dialog.GetValue()
            result = translate(input_text)
            ResultWindow(result, ("Translation Result"))
        dialog.Destroy()
