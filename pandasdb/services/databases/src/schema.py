from functools import lru_cache

import networkx as nx

from pandasdb.communication.errors.io import PandasDBIOError
from pandasdb.libraries.overrides.src.lazy import LazyLoader
from pandasdb.libraries.overrides.src.representable import Representable
from pandasdb.services.databases.src.table import Table
from concurrent.futures import TimeoutError
import pandas as pd
from pandasdb.services.databases.src.table_builder import TableBuilder


class Schema(LazyLoader, Representable):

    def __init__(self, name, database):
        LazyLoader.__init__(self)
        Representable.__init__(self)
        self.name = name
        self.database = database
        self.tables = []

    def __setup__(self, timeout=20):
        # @no:format
        tables_future = self.database.inspect(lambda inspect: inspect.get_table_names(schema=self.name), asynchronous=True)
        views_future = self.database.inspect(lambda inspect: inspect.get_view_names(schema=self.name), asynchronous=True)

        try:
            for name in tables_future.result(timeout=timeout):
                setattr(self, name, Table(name=name, schema=self, is_view=False))
                self.tables.append(name)

            for name in views_future.result(timeout=timeout):
                setattr(self, name, Table(name=name, schema=self, is_view=True))
                self.tables.append(name)

            self.tables = sorted(self.tables)
        except TimeoutError:
            raise PandasDBIOError(f"Attempt to find tables in {self.name} timed out. This is most likely a connection or permission issue")

        if not self.tables:
            raise PandasDBIOError(f"Could not find any tables in {self.name}. This is most likely a connection or permission issue")
        # @do:format

    @property
    @lru_cache
    def graph(self):
        graph = self.database.inspect(lambda inspect: inspect.get_sorted_table_and_fkc_names(schema=self.name), timeout=20)
        G = nx.DiGraph()
        return graph

    def Table(self, name: str) -> TableBuilder:
        return TableBuilder(self, name)

    def head(self):
        if self.tables:
            return pd.DataFrame({"tables": self.tables})

    def __on_head_failure__(self):
        print(
            f"Failed to find any tables in {self.database.name}.{self.name} for user {self.database.configuration.username}. This is most likely a connection or permission issue.")
