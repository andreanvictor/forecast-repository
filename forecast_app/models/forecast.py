from django.db import models
from django.urls import reverse

from forecast_app.models.forecast_model import ForecastModel
from forecast_app.models.project import TimeZero
from utils.utilities import basic_str


class Forecast(models.Model):
    """
    Represents a model's forecasted data. There are one or more Forecasts for each of my ForecastModel's Project's
    TimeZeros. Supports versioning via this 3-tuple: (forecast_model__id, time_zero__id, issue_date). That is, a
    Forecast's "version" is the combination of those three. Put another way, within a ForecastModel, a forecast's
    version is the (time_zero, issue_date) 2-tuple.
    """


    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['forecast_model', 'time_zero', 'issue_date'], name='unique_version'),
        ]


    forecast_model = models.ForeignKey(ForecastModel, related_name='forecasts', on_delete=models.CASCADE)

    source = models.TextField(help_text="file name of the source of this forecast's prediction data")

    # NB: these TimeZeros must be the exact objects as the ones in my ForecastModel's Project, b/c there is no __eq__()
    time_zero = models.ForeignKey(TimeZero, on_delete=models.CASCADE,
                                  help_text="TimeZero that this forecast is in relation to.")

    # when this instance was created. basically the post-validation save date:
    created_at = models.DateTimeField(auto_now_add=True)

    # this Forecast's version - Forecast versions are named/identified by `issue_date`. defaults to the date at time of
    # creation. only special users can edit this due wanting to implement some scientific integrity controls
    issue_date = models.DateField(auto_now_add=True, db_index=True)

    # arbitrary information about this forecast
    notes = models.TextField(null=True, blank=True,
                             help_text="Text describing anything slightly different about a given forecast, e.g., a "
                                       "changed set of assumptions or a comment about when the forecast was created. "
                                       "Notes should be brief, typically less than 50 words.")


    def __repr__(self):
        return str((self.pk, self.time_zero, self.issue_date, self.source, self.created_at))


    def __str__(self):  # todo
        return basic_str(self)


    def get_absolute_url(self):
        return reverse('forecast-detail', args=[str(self.pk)])


    def get_class(self):
        """
        :return: view utility that simply returns a my class as a string. used by delete_modal_snippet.html
        """
        return self.__class__.__name__


    def html_id(self):
        """
        :return: view utility that returns a unique HTML id for this object. used by delete_modal_snippet.html
        """
        return self.__class__.__name__ + '_' + str(self.pk)


    @property
    def name(self):
        """
        We define the name property so that delete_modal_snippet.html can show something identifiable when asking to
        confirm deleting a Forecast. All other deletable models have 'name' fields (Project and ForecastModel).
        """
        return self.source
