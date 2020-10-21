#!/usr/bin/env python
import os
import importlib


from django.core.management import execute_from_command_line as execute


def execute_from_command_line(argv=None):
    """
    allow specific mapping of settings files to be expressed in settings file
    """
    current_settings = os.environ.get("DJANGO_SETTINGS_MODULE")
    settings = importlib.import_module(current_settings)

    if hasattr(settings, "COMMAND_SPECIFIC_SETTINGS") and argv:
        specific_settings = settings.COMMAND_SPECIFIC_SETTINGS

        #make sure settings aren't being manually configured
        has_options = [x for x in argv if "--settings" in x]
        if len(has_options) == 0:
            for command, settings_file in specific_settings:
                if command in argv:
                    argv.append("--settings={file}".format(file=settings_file))
                    break

    execute(argv)
