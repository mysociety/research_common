import sqlite3

from django.apps import AppConfig
from django.conf import settings
from django.db import connections

django_table = """CREATE TABLE IF
NOT EXISTS "django_content_type" (
 "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
 "app_label" varchar(100) NOT NULL,
 "model" varchar(100) NOT NULL
);"""


class ResearchCommonConfig(AppConfig):
    name = 'research_common'

    def load_to_memory(self, source_name, dest_name):
       
        databases = settings.DATABASES
        print("Copying database to memory for faster performance")
        con = sqlite3.connect(databases[source_name]["NAME"])
        dest_con = connections[dest_name]

        # set up the memory table to accept data
        cursor = dest_con.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute(django_table)
        dest_con.commit()

        count = 0
        changed = False
        # read from file to memory database
        for line in con.iterdump():
            count += 1
            if count % 100000 == 0:
                print(count)
            # need to create the content type table to load, but then will run into trouble
            # when importing, so change that line as we go
            if changed is False and 'CREATE TABLE "django_content_type"' in line:
                changed = True
                line = line.replace('CREATE TABLE "django_content_type"',
                                    'CREATE TABLE IF NOT EXISTS "django_content_type"')
            cursor.execute(line)

        dest_con.commit()
        con.close()

        print("Database load complete.")

    def ready(self):
        """
        if a database is configured as memory source, will
        assume the default database is a memory waiting to be uploaded
        """
        source_name = "memory_source"
        dest_name = "default"

        if source_name in settings.DATABASES:
            self.load_to_memory(source_name, dest_name)
