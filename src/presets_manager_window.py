# presets_manager_window.py
#
# Change the look of Adwaita, with ease
# Copyright (C) 2022  Gradience Team
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import os
import shutil
import json

from gi.repository import Gtk, Adw, Gio, Gdk, GLib

from .preset_row import GradiencePresetRow
from .builtin_preset_row import GradienceBuiltinPresetRow
from .explore_preset_row import GradienceExplorePresetRow
from .modules.custom_presets import fetch_presets
from .constants import rootdir, build_type
from .modules.utils import to_slug_case
from .repo_row import GradienceRepoRow

PRESETS_LIST_URL = "https://github.com/GradienceTeam/Community/raw/main/presets.json"


@Gtk.Template(resource_path=f"{rootdir}/ui/presets_manager_window.ui")
class GradiencePresetWindow(Adw.Window):
    __gtype_name__ = "GradiencePresetWindow"

    installed = Gtk.Template.Child()
    repos = Gtk.Template.Child()
    main_view = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()

    import_button = Gtk.Template.Child("import_button")
    remove_button = Gtk.Template.Child("remove_button")
    file_manager_button = Gtk.Template.Child("file_manager_button")

    search_entry = Gtk.Template.Child("search_entry")
    search_stack = Gtk.Template.Child("search_stack")
    search_results = Gtk.Template.Child("search_results")
    search_spinner = Gtk.Template.Child("search_spinner")

    custom_presets = {}

    official_repositories = {
        "Official": "https://github.com/GradienceTeam/Community/raw/main/presets.json"}

    search_results_list = []

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)

        self.settings = parent.settings
        self.user_repositories = self.settings.get_value("repos").unpack()
        self.enabled_repos = self.settings.get_value("enabled-repos").unpack()
        self.repos_list = Adw.PreferencesGroup()
        self.repos_list.set_title(_("Repositories"))
        self.repos.add(self.repos_list)
        self.reload_repos_group()

        self.builtin_preset_list = Adw.PreferencesGroup()
        self.builtin_preset_list.set_title(_("Builtin Presets"))
        self.installed.add(self.builtin_preset_list)

        self.preset_list = Adw.PreferencesGroup()
        self.preset_list.set_title(_("User Presets"))
        self.installed.add(self.preset_list)
        self.reload_pref_group()

        self.app = Gtk.Application.get_default()
        self.setup_explore()
        self.setup_import()

        self.connect_signals()

        self.delete_toast = Adw.Toast(title=_("Preset removed"))
        # self.delete_toast.set_action_name("on_undo_button_clicked")
        self.delete_preset = True
        self.delete_toast.set_button_label(_("Undo"))
        self.delete_toast.connect("dismissed", self.on_delete_toast_dismissed)
        self.delete_toast.connect(
            "button-clicked",
            self.on_undo_button_clicked)

    def remove_repo(self, repo_name):
        self.user_repositories.pop(repo_name)
        self.settings.set_value(
            "repos", GLib.Variant(
                "a{sv}", self.user_repositories))
        self.reload_repos_group()
        self.setup_explore()

    def reload_repos_group(self):
        self.repos.remove(self.repos_list)
        self.repos_list = Adw.PreferencesGroup()
        self.repos_list.set_title(_("Repositories"))
        
        self.add_repo_button = Gtk.Button.new_from_icon_name("list-add-symbolic")
        self.add_repo_button.connect("clicked", self.on_add_repo_button_clicked)
        
        self.repos_list.set_header_suffix(self.add_repo_button)
        
        for repo_name, repo in self.official_repositories.items():
            row = GradienceRepoRow(repo, repo_name, self, deletable=False)
            self.repos_list.add(row)

        for repo_name, repo in self.user_repositories.items():
            row = GradienceRepoRow(repo, repo_name, self)
            self.repos_list.add(row)

        self.repos.add(self.repos_list)

        self._repos = {**self.user_repositories, **self.official_repositories}
        
        
    def add_repo(self, repo_name, repo_url):
        self.user_repositories[repo_name] = repo_url
        self.settings.set_value(
            "repos", GLib.Variant(
                "a{sv}", self.user_repositories))
        self.reload_repos_group()
    def on_add_repo_button_clicked(self, *args):
        print("add new repo")
        

    def setup_explore(self):
        for widget in self.search_results_list:
            self.search_results.remove(widget)
        for repo_name, repo in self._repos.items():
            self.explore_presets, urls = fetch_presets(repo)

            if not self.explore_presets:  # offline
                self.search_spinner.props.visible = False
                self.search_stack.set_visible_child_name("page_offline")
            else:
                self.search_spinner.props.visible = False

                for (preset, preset_name), preset_url in zip(
                        self.explore_presets.items(), urls):
                    row = GradienceExplorePresetRow(
                        preset_name, preset_url, self)
                    self.search_results.append(row)
                    self.search_results_list.append(row)

    def setup_import(self):
        self.file_chooser_dialog = Gtk.FileChooserNative()
        self.file_chooser_dialog.set_transient_for(self)

        self.file_chooser_dialog.connect(
            "response", self.on_file_chooser_response
        )

    def connect_signals(self):
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("realize", self.on_search_realize)

    def on_delete_toast_dismissed(self, widget):
        if self.delete_preset:
            try:
                os.remove(os.path.join(
                    os.environ.get("XDG_CONFIG_HOME",
                                   os.environ["HOME"] + "/.config"),
                    "presets",
                    to_slug_case(self.old_name) + ".json",
                ))
            except Exception:
                self.toast_overlay.add_toast(
                    Adw.Toast(title=_("Unable to delete preset"))
                )
            else:
                self.toast_overlay.add_toast(
                    Adw.Toast(title=_("Preset removed"))
                )
            finally:
                self.reload_pref_group()

        self.delete_preset = True

    def on_undo_button_clicked(self, *_args):
        self.delete_preset = False
        self.delete_toast.dismiss()

    def on_search_changed(self, widget):
        print("search changed")

    def on_search_realize(self, widget):
        print("search realized")

    @Gtk.Template.Callback()
    def on_file_manager_button_clicked(self, *_args):
        self.app.open_preset_directory()

    @Gtk.Template.Callback()
    def on_import_button_clicked(self, *_args):
        self.file_chooser_dialog.show()

    def on_file_chooser_response(self, widget, response):
        if response == Gtk.ResponseType.ACCEPT:
            self.preset_path = self.file_chooser_dialog.get_file()
            preset_file = self.preset_path.get_basename()
        self.file_chooser_dialog.hide()

        if response == Gtk.ResponseType.ACCEPT:
            if preset_file.endswith(".json"):

                if preset_file.strip(".json") in self.custom_presets:
                    self.toast_overlay.add_toast(
                        Adw.Toast(title=_("Preset already exists"))
                    )
                else:
                    shutil.copy(self.preset_path.get_path(), os.path.join(
                        os.environ.get("XDG_CONFIG_HOME",
                                       os.environ["HOME"] + "/.config"),
                        "presets",
                        preset_file
                    ))
                    self.toast_overlay.add_toast(
                        Adw.Toast(title=_("Preset imported"))
                    )
            else:
                self.toast_overlay.add_toast(Adw.Toast(
                    title=_("Unsupported file format, must be .json")))

        self.reload_pref_group()

    def reload_pref_group(self):
        preset_directory = os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.environ["HOME"] + "/.config"),
            "presets",
        )
        if not os.path.exists(preset_directory):
            os.makedirs(preset_directory)

        self.custom_presets.clear()
        self.builtin_presets = {
            "adwaita-dark": "Adwaita Dark",
            "adwaita": "Adwaita",
            "pretty-purple": "Pretty Purple",
        }
        for file_name in os.listdir(preset_directory):
            if file_name.endswith(".json"):
                try:
                    with open(
                        os.path.join(preset_directory, file_name), "r", encoding="utf-8"
                    ) as file:
                        preset_text = file.read()
                    preset = json.loads(preset_text)
                    if preset.get("variables") is None:
                        raise KeyError("variables")
                    if preset.get("palette") is None:
                        raise KeyError("palette")
                    self.custom_presets[file_name.replace(
                        ".json", "")] = preset["name"]
                except Exception:
                    self.toast_overlay.add_toast(
                        Adw.Toast(title=_("Failed to load preset"))
                    )
        self.installed.remove(self.preset_list)
        self.installed.remove(self.builtin_preset_list)

        self.builtin_preset_list = Adw.PreferencesGroup()
        self.builtin_preset_list.set_title(_("Builtin Presets"))
        for preset, preset_name in self.builtin_presets.items():
            row = GradienceBuiltinPresetRow(preset_name, self.toast_overlay)
            self.builtin_preset_list.add(row)
        self.installed.add(self.builtin_preset_list)

        self.preset_list = Adw.PreferencesGroup()
        self.preset_list.set_title(_("User Presets"))
        self.preset_list.set_description(
            _("See <a href=\"https://github.com/GradienceTeam/Community\">GradienceTeam/Community</a> on Github for more presets"))

        if self.custom_presets:
            for preset, preset_name in self.custom_presets.items():
                row = GradiencePresetRow(preset_name, self)
                self.preset_list.add(row)
        else:
            self.preset_empty = Adw.ActionRow()
            self.preset_empty.set_title(
                _("No preset found! Use the import button to import one or search one on the Explore tab"))
            self.preset_list.add(self.preset_empty)
        self.installed.add(self.preset_list)
