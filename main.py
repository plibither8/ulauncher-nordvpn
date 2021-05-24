import os
import os.path
import json
import pathlib
from fuzzysearch import find_near_matches
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import (
    KeywordQueryEvent,
    ItemEnterEvent,
    PreferencesEvent,
    PreferencesUpdateEvent,
)
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction


def get_path(filename):
    current_dir = pathlib.Path(__file__).parent.absolute()
    return f"{current_dir}/{filename}"


class Nord:
    nordvpn_bin_paths = ["/usr/bin/nordvpn", "/bin/nordvpn"]
    countries = []
    previously_connected = []

    def get_installed_path(self):
        for path in self.nordvpn_bin_paths:
            if os.path.exists(path):
                return path
        return False

    def is_installed(self):
        return bool(self.installed_path)

    def connect(self, country_value):
        if not self.is_installed():
            return
        if country_value not in list(
            map(lambda c: c["value"], self.previously_connected)
        ):
            country_data = next(
                (c for c in self.countries if c["value"] == country_value), None
            )
            if country_data:
                self.previously_connected.insert(0, country_data)
        os.system(f"{self.installed_path} connect {country_value}")

    def disconnect(self):
        if not self.is_installed():
            return
        os.system(f"{self.installed_path} disconnect")

    def __init__(self):
        self.countries = json.load(open(get_path("countries.json"), "r"))
        self.installed_path = self.get_installed_path()


class NordExtension(Extension):
    keyword = None

    def __init__(self):
        super(NordExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())
        self.subscribe(PreferencesEvent, PreferencesEventListener())
        self.subscribe(PreferencesUpdateEvent, PreferencesUpdateEventListener())
        self.nord = Nord()

    def get_countries_by_fuzzy(self, query):
        data = Nord().previously_connected[:]
        for country in Nord().countries:
            if country not in data:
                data.append(country)
        if not query:
            return data[0:10]

        result = []
        for country in data:
            name = country["label"]
            a = find_near_matches(query, name, max_l_dist=1)
            if len(a) and a[0].matched:
                result.append((country, a[0].dist))

        return list(map(lambda r: r[0], sorted(result, key=lambda r: r[1])))[0:10]

    def get_country_ext_result_items(self, query):
        items = []
        for country in self.get_countries_by_fuzzy(query):
            items.append(
                ExtensionResultItem(
                    icon=get_path(f'images/flags/{country["code"]}.svg'),
                    name=country["label"],
                    on_enter=ExtensionCustomAction(
                        {
                            "action": "CONNECT_TO_COUNTRY",
                            "country": country["value"],
                        }
                    ),
                )
            )
        return items


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        items = []

        if not extension.nord.is_installed():
            items.append(
                ExtensionResultItem(
                    icon=get_path("images/icon.svg"),
                    name="NordVPN not installed :/",
                    description="Looks like the NordVPN CLI is not installed on your system!",
                    highlightable=False,
                    on_enter=HideWindowAction(),
                )
            )
            return RenderResultListAction(items)

        argument = event.get_argument() or ""
        command, country_query = (argument.split(" ") + [None])[:2]
        if command in ["connect"]:
            items.extend(extension.get_country_ext_result_items(country_query))
            return RenderResultListAction(items)

        items.extend(
            [
                ExtensionResultItem(
                    icon=get_path("images/icon.svg"),
                    name="Connect",
                    description="Connect to NordVPN: choose from a list of countries",
                    highlightable=False,
                    on_enter=SetUserQueryAction(
                        f'{extension.keyword or "nord"} connect '
                    ),
                ),
                ExtensionResultItem(
                    icon=get_path("images/icon.svg"),
                    name="Disconnect",
                    description="Disconnect from NordVPN",
                    on_enter=ExtensionCustomAction({"action": "DISCONNECT"}),
                ),
            ]
        )
        return RenderResultListAction(items)


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        data = event.get_data()
        action = data["action"]

        if action == "CONNECT":
            return RenderResultListAction(extension.get_country_ext_result_items())

        if action == "DISCONNECT":
            return extension.nord.disconnect()

        if action == "CONNECT_TO_COUNTRY":
            return extension.nord.connect(data["country"])


class PreferencesEventListener(EventListener):
    def on_event(self, event, extension):
        extension.keyword = event.preferences["nord_kw"]


class PreferencesUpdateEventListener(EventListener):
    def on_event(self, event, extension):
        if event.id == "nord_kw":
            extension.keyword = event.new_value


if __name__ == "__main__":
    NordExtension().run()
