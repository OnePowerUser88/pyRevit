# -*- coding: utf-8 -*-
"""Open Extension Config window to edit per-extension options (from extension.ini)."""
from pyrevit.forms import extension_config_window

if extension_config_window.show_extension_config():
    from pyrevit import forms
    forms.alert("Extension config saved.\nReload pyRevit to apply (e.g. disabled tabs).")
