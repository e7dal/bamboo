import simplejson as json
from math import isnan
import re
from calendar import timegm

from dateutil.parser import parse as date_parse
import numpy as np
from pandas import Series

from bamboo.lib.constants import DATETIME, ERROR, MONGO_RESERVED_KEYS,\
    MONGO_RESERVED_KEY_PREFIX, SIMPLETYPE
from bamboo.config.settings import ASYNCHRONOUS_TASKS

"""
Constants for utils
"""

# JSON encoding string
JSON_NULL = 'null'

# delimiter when passing multiple groups as a string
GROUP_DELIMITER = ','


def is_float_nan(num):
    return isinstance(num, float) and isnan(num)


def is_potential_date(value):
    return not (is_float_nan(value) or isinstance(value, bool))


def get_json_value(value):
    if is_float_nan(value):
        value = JSON_NULL
    elif isinstance(value, np.int64):
        value = int(value)
    elif isinstance(value, np.bool_):
        value = bool(value)
    return value


def series_to_jsondict(series):
    return series if series is None else dict([
        (unicode(key), get_json_value(value))
        for key, value in series.iteritems()
    ])


def df_to_jsondict(dframe):
    return [series_to_jsondict(series) for idx, series in dframe.iterrows()]


def dump_or_error(data, error_message):
    if data is None:
        data = {ERROR: error_message}
    return json.dumps(data)


def prefix_reserved_key(key, prefix=MONGO_RESERVED_KEY_PREFIX):
    """
    Prefix reserved key
    """
    return '%s%s' % (prefix, key)


def slugify_columns(column_names):
    """
    Convert non-alphanumeric characters in column names into underscores and
    ensure that all column names are unique.
    """
    # we need to change this to deal with the following conditions:
    # * _id as a key (mongo)
    # * keys that start with a $ or contain a . (mongo)
    # * keys that contain spaces or operators (parsing)
    encode_column_re = re.compile(r'\W')

    encoded_names = []

    for column_name in column_names:
        new_col_name = encode_column_re.sub('_', column_name).lower()
        while new_col_name in encoded_names:
            new_col_name += '_'
        encoded_names.append(new_col_name)
    return encoded_names


def recognize_dates(dframe):
    """
    Check if object columns in a dataframe can be parsed as dates.
    If yes, rewrite column with values parsed as dates.
    """
    for idx, dtype in enumerate(dframe.dtypes):
        if dtype.type == np.object_:
            dframe = _convert_column_to_date(dframe, dframe.columns[idx])
    return dframe


def recognize_dates_from_schema(dataset, dframe):
    # if it is a date column, recognize dates
    dframe_columns = dframe.columns.tolist()
    for column, column_schema in dataset.schema.items():
        if column in dframe_columns and\
                column_schema[SIMPLETYPE] == DATETIME:
            dframe = _convert_column_to_date(dframe, column)
    return dframe


def _convert_column_to_date(dframe, column):
    try:
        new_column = Series([
            date_parse(field) if is_potential_date(field) else field for
            field in dframe[column].tolist()])
        dframe[column] = new_column
    except ValueError:
        # it is not a correctly formatted date
        pass
    except OverflowError:
        # it is a number that is too large to be a date
        pass
    return dframe


def parse_str_to_unix_time(value):
    return parse_date_to_unix_time(date_parse(value))


def parse_date_to_unix_time(date):
    return timegm(date.utctimetuple())


def reserve_encoded(string):
    return prefix_reserved_key(string) if string in MONGO_RESERVED_KEYS else\
        string


def split_groups(group_str):
    return group_str.split(GROUP_DELIMITER)


def call_async(function, dataset, *args, **kwargs):
    if ASYNCHRONOUS_TASKS:
        function.__getattribute__('apply_async')(
            args=args, kwargs=kwargs, queue=dataset.dataset_id)
    else:  # pragma: no cover
        function(*args, **kwargs)
