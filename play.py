import datetime

from forecast_app.models import DataFile, Project, Target, TimeZero, ForecastModel, Forecast


#
# print and delete all user objects
#

for model_class in [DataFile, Project, Target, TimeZero, ForecastModel, Forecast]:
    print(model_class, model_class.objects.all())

for model_class in [DataFile, Project, Target, TimeZero, ForecastModel, Forecast]:
    model_class.objects.all().delete()

#
# create the CDC Flu challenge (2016-2017) project and targets
#

df = DataFile.objects.create(
    location='https://github.com/reichlab/2016-2017-flu-contest-ensembles/tree/master/data-raw',
    file_type='z')  # todo s/b zip file

p = Project.objects.create(
    name='CDC Flu challenge (2016-2017)',
    description='Code, results, submissions, and method description for the 2016-2017 CDC flu contest submissions based on ensembles.',
    url='https://github.com/reichlab/2016-2017-flu-contest-ensembles',
    core_data=df)

# p = Project.objects.get(name='CDC Flu challenge (2016-2017)')
# p.pk

for target_name in ['Season onset', 'Season peak week', 'Season peak percentage', '1 wk ahead', '2 wk ahead',
                    '3 wk ahead', '4 wk ahead']:
    Target.objects.create(project=p, name=target_name, description='{} description TBD'.format(target_name))

p.target_set.all()

#
# create the project's TimeZeros. Note: the project has no version_dates.
#

# https://ibis.health.state.nm.us/resource/MMWRWeekCalendar.html
# dict: {week_number: (2016 date, 2017 date), ...}
MMWR_WEEK_TO_2016_17_TUPLE = {
    1: ('1/16/2016', '1/14/2017'),
    2: ('1/16/2016', '1/14/2017'),
    3: ('1/23/2016', '1/21/2017'),
    4: ('1/30/2016', '1/28/2017'),
    5: ('2/6/2016', '2/4/2017'),
    6: ('2/13/2016', '2/11/2017'),
    7: ('2/20/2016', '2/18/2017'),
    8: ('2/27/2016', '2/25/2017'),
    9: ('3/5/2016', '3/4/2017'),
    10: ('3/12/2016', '3/11/2017'),
    11: ('3/19/2016', '3/18/2017'),
    12: ('3/26/2016', '3/25/2017'),
    13: ('4/2/2016', '4/1/2017'),
    14: ('4/9/2016', '4/8/2017'),
    15: ('4/16/2016', '4/15/2017'),
    16: ('4/23/2016', '4/22/2017'),
    17: ('4/30/2016', '4/29/2017'),
    18: ('5/7/2016', '5/6/2017'),
    19: ('5/14/2016', '5/13/2017'),
    20: ('5/21/2016', '5/20/2017'),
    21: ('5/28/2016', '5/27/2017'),
    22: ('6/4/2016', '6/3/2017'),
    23: ('6/11/2016', '6/10/2017'),
    24: ('6/18/2016', '6/17/2017'),
    25: ('6/25/2016', '6/24/2017'),
    26: ('7/2/2016', '7/1/2017'),
    27: ('7/9/2016', '7/8/2017'),
    28: ('7/16/2016', '7/15/2017'),
    29: ('7/23/2016', '7/22/2017'),
    30: ('7/30/2016', '7/29/2017'),
    31: ('8/6/2016', '8/5/2017'),
    32: ('8/13/2016', '8/12/2017'),
    33: ('8/20/2016', '8/19/2017'),
    34: ('8/27/2016', '8/26/2017'),
    35: ('9/3/2016', '9/2/2017'),
    36: ('9/10/2016', '9/9/2017'),
    37: ('9/17/2016', '9/16/2017'),
    38: ('9/24/2016', '9/23/2017'),
    39: ('10/1/2016', '9/30/2017'),
    40: ('10/8/2016', '10/7/2017'),
    41: ('10/15/2016', '10/14/2017'),
    42: ('10/22/2016', '10/21/2017'),
    43: ('10/29/2016', '10/28/2017'),
    44: ('11/5/2016', '11/4/2017'),
    45: ('11/12/2016', '11/11/2017'),
    46: ('11/19/2016', '11/18/2017'),
    47: ('11/26/2016', '11/25/2017'),
    48: ('12/3/2016', '12/2/2017'),
    49: ('12/10/2016', '12/9/2017'),
    50: ('12/17/2016', '12/16/2017'),
    51: ('12/24/2016', '12/23/2017'),
    52: ('12/31/2016', '12/30/2017'),
    53: ('', ''),
}


def mmwr_year_week_num_to_date(mmwr_year_week_num):  # ex: '2016-43'
    mmwr_year = mmwr_year_week_num.split('-')[0]
    mmwr_week_number = mmwr_year_week_num.split('-')[1]
    week_num_2016_17_tuple = MMWR_WEEK_TO_2016_17_TUPLE[int(mmwr_week_number)]
    m_d_y = week_num_2016_17_tuple[0] if mmwr_year == '2016' else week_num_2016_17_tuple[1]
    month = int(m_d_y.split('/')[0])
    day = int(m_d_y.split('/')[1])
    year = int(m_d_y.split('/')[2])
    return datetime.date(year, month, day)


for mmwr_year_week_num in ['2016-43', '2016-44', '2016-45', '2016-46', '2016-47', '2016-48', '2016-49', '2016-50',
                           '2016-51', '2016-52', '2017-1', '2017-10', '2017-11', '2017-12', '2017-13', '2017-14',
                           '2017-15', '2017-16', '2017-17', '2017-18', '2017-2', '2017-3', '2017-4', '2017-5',
                           '2017-6', '2017-7', '2017-8', '2017-9']:
    TimeZero.objects.create(project=p,
                            timezero_date=str(mmwr_year_week_num_to_date(mmwr_year_week_num)),
                            version_date=None)

p.timezero_set.all()

#
# create the project's ForecastModel
#

xx  # TODO

#
# create the ForecastModel's Forecasts
#

xx  # TODO
