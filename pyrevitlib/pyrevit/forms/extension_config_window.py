# -*- coding: utf-8 -*-
"""Extension config window: edit per-extension options from extension.ini manifest.

Values are stored in pyRevit_config.ini under [ExtensionName.extension] as single values.
CLI can read/write the same keys via the same INI.

Usage:
    from pyrevit.forms import extension_config_window
    if extension_config_window.show_extension_config():
        print("Config saved. Reload pyRevit to apply.")
"""

import os
import os.path as op

from pyrevit import forms
from pyrevit.userconfig import user_config

EXTENSION_INI_FILENAME = "extension.ini"

TYPE_STRING = "string"
TYPE_BOOL = "bool"
TYPE_STRING_LIST = "string_list"
TYPE_CHOICE = "choice"


def _parse_extension_ini(ext_dir):
    """Parse extension.ini in ext_dir. Returns list of option defs."""
    path = op.join(ext_dir, EXTENSION_INI_FILENAME)
    if not op.isfile(path):
        return []
    result = []
    current_section = None
    current_keys = {}

    def flush_section():
        if not current_section:
            return
        type_str = (current_keys.get("type") or "string").strip().lower()
        if type_str in ("boolean",):
            type_str = TYPE_BOOL
        elif type_str in ("stringlist",):
            type_str = TYPE_STRING_LIST
        opts = []
        if type_str == TYPE_CHOICE and current_keys.get("options"):
            opts = [x.strip() for x in current_keys["options"].split(",") if x.strip()]
        result.append({
            "key": current_section,
            "type": type_str,
            "label": (current_keys.get("label") or current_section).strip(),
            "description": (current_keys.get("description") or "").strip(),
            "default": (current_keys.get("default") or "").strip(),
            "options": opts,
        })

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                flush_section()
                current_section = line[1:-1].strip()
                current_keys = {}
                continue
            eq = line.find("=")
            if eq > 0 and current_section:
                k = line[:eq].strip()
                v = line[eq + 1:].strip()
                current_keys[k] = v
    flush_section()
    return result


def _get_extensions_with_config():
    """Return list of (display_name, ext_dir, section_name) for extensions that have extension.ini."""
    try:
        roots = user_config.core.userextensions
    except Exception:
        roots = []
    if not isinstance(roots, list):
        roots = [roots] if roots else []
    result = []
    seen = set()
    for root in roots:
        if not root or not op.isdir(root):
            continue
        try:
            for name in os.listdir(root):
                if not name.lower().endswith(".extension"):
                    continue
                ext_dir = op.join(root, name)
                if not op.isdir(ext_dir):
                    continue
                if ext_dir in seen:
                    continue
                seen.add(ext_dir)
                if not op.isfile(op.join(ext_dir, EXTENSION_INI_FILENAME)):
                    continue
                section_name = name
                display_name = name[:-len(".extension")] if name.lower().endswith(".extension") else name
                result.append((display_name, ext_dir, section_name))
        except Exception:
            continue
    return result


def _get_value_raw(section, key, default=""):
    try:
        if user_config._parser.has_section(section) and user_config._parser.has_option(section, key):
            return user_config._parser.get(section, key) or ""
    except Exception:
        pass
    return default or ""


def _set_value_raw(section, key, value):
    if not user_config._parser.has_section(section):
        user_config._parser.add_section(section)
    user_config._parser.set(section, key, value or "")


def show_extension_config():
    """Show the extension config window. Returns True if user saved."""
    extensions = _get_extensions_with_config()
    if not extensions:
        forms.alert("No extensions with extension.ini found.\n\nAdd extension.ini to your extension root to declare config options.")
        return False

    choices = [disp for disp, _path, _sec in extensions]
    res = forms.SelectFromList.show(choices, title="Select extension to configure", button_name="Configure")
    if not res:
        return False
    idx = choices.index(res)
    _display_name, ext_dir, section_name = extensions[idx]
    schema = _parse_extension_ini(ext_dir)
    if not schema:
        forms.alert("No options in extension.ini.")
        return False

    # Show simple dialog: string, bool, choice only; raw get/set
    try:
        dlg = _ExtensionConfigDialog(schema, section_name, "Extension config: {}".format(res))
        if dlg.show_dialog():
            user_config.save_changes()
            return True
    except Exception as e:
        forms.alert("Error: {}".format(e))
    return False


class _ExtensionConfigDialog(forms.WPFWindow):
    """Minimal WPF dialog for extension config: raw INI get/set, string/bool/choice only."""

    def __init__(self, schema, section_name, title, width=450):
        self._schema = schema
        self._section = section_name
        self._title = title
        self._width = width
        self._saved = False
        xaml = self._build_xaml()
        forms.WPFWindow.__init__(self, xaml, literal_string=True)
        self.Title = title
        self._load_values()
        self.save_button.Click += self._on_save
        self.cancel_button.Click += self._on_cancel

    def _escape(self, text):
        if not text:
            return ""
        return (str(text)
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;").replace("'", "&apos;"))

    def _build_xaml(self):
        parts = [
            '<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"',
            '        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"',
            '        Title="Extension Config" Height="Auto" Width="{}"'.format(self._width),
            '        WindowStartupLocation="CenterScreen" ResizeMode="CanResizeWithGrip"',
            '        SizeToContent="Height">',
            '    <Grid Margin="20">',
            '        <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>',
            '        <StackPanel Grid.Row="0" Margin="0,0,0,12">',
        ]
        for opt in self._schema:
            name = self._escape(opt["key"])
            label = self._escape(opt["label"])
            t = opt["type"]
            if t == TYPE_BOOL:
                parts.append('<CheckBox x:Name="{}" Content="{}"/>'.format(name, label))
            elif t == TYPE_CHOICE:
                parts.append('<Label Content="{}"/>'.format(label))
                parts.append('<ComboBox x:Name="{}"/>'.format(name))
            else:
                parts.append('<Label Content="{}"/>'.format(label))
                parts.append('<TextBox x:Name="{}"/>'.format(name))
        parts.extend([
            "        </StackPanel>",
            '        <StackPanel Grid.Row="1" Orientation="Horizontal" HorizontalAlignment="Right">',
            '            <Button x:Name="save_button" Content="Save" Width="80" Height="30" Margin="0,0,10,0" IsDefault="True"/>',
            '            <Button x:Name="cancel_button" Content="Cancel" Width="80" Height="30" IsCancel="True"/>',
            "        </StackPanel>",
            "    </Grid>",
            "</Window>",
        ])
        return "\n".join(parts)

    def _load_values(self):
        for opt in self._schema:
            key = opt["key"]
            default = opt.get("default") or ""
            val = _get_value_raw(self._section, key, default)
            ctrl = getattr(self, key, None)
            if not ctrl:
                continue
            t = opt["type"]
            if t == TYPE_BOOL:
                ctrl.IsChecked = str(val).lower() in ("true", "1", "yes")
            elif t == TYPE_CHOICE:
                opts = opt.get("options") or []
                ctrl.ItemsSource = opts
                if val in opts:
                    ctrl.SelectedItem = val
                elif opts:
                    ctrl.SelectedIndex = 0
            else:
                ctrl.Text = val

    def _on_save(self, sender, args):
        for opt in self._schema:
            key = opt["key"]
            ctrl = getattr(self, key, None)
            if not ctrl:
                continue
            t = opt["type"]
            if t == TYPE_BOOL:
                val = "true" if ctrl.IsChecked else "false"
            elif t == TYPE_CHOICE:
                val = str(ctrl.SelectedItem) if ctrl.SelectedItem else ""
            else:
                val = ctrl.Text if ctrl.Text else ""
            _set_value_raw(self._section, key, val)
        self._saved = True
        self.Close()

    def _on_cancel(self, sender, args):
        self.Close()

    def show_dialog(self):
        self.ShowDialog()
        return self._saved
