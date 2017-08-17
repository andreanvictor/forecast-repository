from django.db import models


def basic_str(obj):
    return obj.__class__.__name__ + ': ' + obj.__repr__()


class DataFile(models.Model):
    """
    A data file located somewhere - server, cloud, document store, etc. For now we presume the file is locatable as a
    URL.
    """
    location = models.URLField(help_text="The data file's location - server, cloud, document store, etc.")

    FILE_TYPES = (
        ('d', 'Directory'),
        ('z', 'Zip File'),
        ('c', 'CDC Forecast File'),  # CSV data file in CDC standard format (points and binned distributions)
    )
    file_type = models.CharField(max_length=1, choices=FILE_TYPES, blank=True, help_text="The data file's type")


    def __repr__(self):
        return str((self.pk, self.file_type, self.location))


    def __str__(self):  # todo
        return basic_str(self)


class Project(models.Model):
    """
    The main class representing a forecast challenge, including metadata, core data, targets, and model entries.
    """
    name = models.CharField(max_length=200)

    description = models.CharField(max_length=2000,
                                   help_text="A few paragraphs describing the project. Includes info about "
                                             "'real-time-ness' of data, i.e., revised/unrevised")

    url = models.URLField(help_text="The project's site")

    # documents (e.g., CSV files) in one zip file. includes all data sets made available to everyone in the challenge,
    # including supplemental data like google queries or weather.
    # constraint: file_type = 'z'
    core_data = models.ForeignKey(DataFile, on_delete=models.SET_NULL, null=True)


    def __repr__(self):
        return str((self.pk, self.name))


    def __str__(self):  # todo
        return basic_str(self)


class Target(models.Model):
    """
    Represents a project's target - a description of the desired data in the each forecast's data file.
    """
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True)

    name = models.CharField(max_length=200)

    description = models.CharField(max_length=2000, help_text="A few paragraphs describing the target")


    def __repr__(self):
        return str((self.pk, self.name))


    def __str__(self):  # todo
        return basic_str(self)


class TimeZero(models.Model):
    """
    A date that a target is relative to. Additionally, contains an optional version_date the specifies the database
    date at which models should work with for this timezero_date date. Akin to rolling back (versioning) the database
    to that date.
     
    Assumes dates from any project can be converted to actual dates, e.g., from Dengue biweeks or CDC MMWR weeks
    ( https://ibis.health.state.nm.us/resource/MMWRWeekCalendar.html ).
    """
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True)

    timezero_date = models.DateField(null=True, blank=True, help_text="A date that a target is relative to")

    version_date = models.DateField(
        null=True, blank=True,
        help_text="the database date at which models should work with for the timezero_date")  # nullable


    def __repr__(self):
        return str((self.pk, self.timezero_date, self.version_date))


    def __str__(self):  # todo
        return basic_str(self)


class ForecastModel(models.Model):
    """
    Represents a project's model entry by a competing team, including metadata, model-specific auxiliary data beyond
    core data, and a list of the actual forecasts.
    """
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True)

    name = models.CharField(max_length=200)

    # should include information on reproducing the model’s results
    description = models.CharField(max_length=2000, help_text="A few paragraphs describing the model")

    url = models.URLField(help_text="The model's development URL")

    # optional model-specific documents in one zip file beyond Project.core_data that were used by the this model.
    # constraint: file_type = 'z'
    auxiliary_data = models.ForeignKey(DataFile, on_delete=models.SET_NULL, null=True, blank=True)  # nullable


    def __repr__(self):
        return str((self.pk, self.name))


    def __str__(self):  # todo
        return basic_str(self)


    def time_zero_for_timezero_date_str(self, timezero_date_str):
        """
        :return: the first TimeZero in forecast_model's Project that has a timezero_date matching timezero_date
        """
        for time_zero in self.project.timezero_set.all():
            if time_zero.timezero_date == timezero_date_str:
                return time_zero

        return None


class Forecast(models.Model):
    """
    Represents a model's forecasted data. There is one Forecast for each of my ForecastModel's Project's TimeZeros.
    """
    forecast_model = models.ForeignKey(ForecastModel, on_delete=models.SET_NULL, null=True)

    # Project.mmwr_year_week_num that this forecast applies to
    time_zero = models.ForeignKey(TimeZero, on_delete=models.SET_NULL, null=True)

    # CSV data file in CDC standard format (points and binned distributions)
    # constraint: file_type = 'c'. must have rows matching Project.targets
    data = models.ForeignKey(DataFile, on_delete=models.SET_NULL, null=True)


    def __repr__(self):
        return str((self.pk, self.time_zero, self.data))


    def __str__(self):  # todo
        return basic_str(self)
