from django_sourdough.views import postlogic, prelogic
from .charts import ChartCollection, BaseChart


class AnchorChartsMixIn(object):
    """
    View for handing where all charts assigned to
    properties of view are added to collection

    ones defined at other levels need to be registered
    with self.chart_collection.register
    """
    chart_storage_slug = ""

    @prelogic
    def create_chart_collection(self):
        """
        create chart collection
        """
        self.chart_collection = ChartCollection(
            self.__class__.chart_storage_slug)

    @postlogic
    def anchor_charts(self):
        """
        assign charts created without assignment to view
        """
        objects = [getattr(self, x) for x in self.values]
        objects = [x for x in objects if isinstance(x, BaseChart)]

        # passes the baking configuration from the command line
        # to the chart renderer
        if hasattr(self.__class__, "baking_options"):
            baking_options = self.__class__.baking_options
        else:
            baking_options = {"baking": False}

        for o in objects:
            self.chart_collection.register(o)

        if self.chart_collection.charts:
            self.chart_collection.export(baking_options)
        else:
            self.chart_collection = None
    anchor_charts.order = 99
