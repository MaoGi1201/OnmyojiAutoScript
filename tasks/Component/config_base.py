# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from datetime import timedelta, time, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic import (BeforeValidator,
                      PlainSerializer,
                      WithJsonSchema,
                      field_serializer,
                      SerializationInfo)
from typing_extensions import Annotated


def format_timedelta(tdelta: timedelta):
    """把 timedelta 格式化为 'DD HH:MM:SS'。"""
    days = tdelta.days
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days:02d} {hours:02d}:{minutes:02d}:{seconds:02d}"

def timedelta_validator(v: Any) -> timedelta:
    """把 'DD HH:MM:SS' 解析成 timedelta（与 format_timedelta 对应）。

    解析失败必须报错：原先对无法识别的字符串直接返回 1 天，
    用户在 GUI 里输入乱码会被静默改成"1 天"，既没提示也很难排查。
    """
    if not isinstance(v, str):
        return v
    match = re.fullmatch(r'\s*(-?)(\d{1,2})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})\s*', v)
    if match is None:
        raise ValueError(f'Invalid time delta: {v!r}, expected "DD HH:MM:SS" (例如 "00 02:00:00")')
    sign, days, hours, minutes, seconds = match.groups()
    delta = TimeDelta(days=int(days), hours=int(hours), minutes=int(minutes), seconds=int(seconds))
    return -delta if sign else delta


def datetime_validator(v: Any) -> datetime:
    if isinstance(v, str):
        return datetime.fromisoformat(v)
    return v


def time_validator(v: Any) -> time:
    if isinstance(v, str):
        return time.fromisoformat(v)
    return v


MultiLine = Annotated[str,
                      WithJsonSchema({'type': 'multi_line'}),]


TimeDelta = Annotated[timedelta,
                      BeforeValidator(timedelta_validator),
                      PlainSerializer(format_timedelta, return_type=str),
                      WithJsonSchema({'type': 'time_delta'}),]

DateTime = Annotated[datetime,
                     BeforeValidator(datetime_validator),
                     PlainSerializer(lambda v: v.strftime('%Y-%m-%d %H:%M:%S') if isinstance(v, datetime) else v, return_type=str),
                     WithJsonSchema({'type': 'date_time'}),]

Time = Annotated[time,
                 BeforeValidator(time_validator),
                 PlainSerializer(lambda v: v.strftime('%H:%M:%S'), return_type=str),
                 WithJsonSchema({'type': 'time'}),]

# ---------------------------------------------------------------------------------------------------------------------

@classmethod
def serializer_exclude(cls, value: any, info: SerializationInfo):
    if info.context and info.context.get('hide', False):
        return 0xABCDEF
    return value


def dynamic_hide(*fields: str,):
    return field_serializer(*fields)(serializer_exclude)


class ConfigBase(BaseModel):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except ValidationError as exc:
            # 初始化失败时用字段默认值兜底，等初始化完成后再重新抛出异常
            exc_info = exc.errors()[0]
            val_error_type = exc_info.get('type', None)
            val_error_key = exc_info.get('loc', None)[0]
            if val_error_type not in ['greater_than_equal',
                                      'greater_than',
                                      'less_than',
                                      'less_than_equal',]:
                raise exc
            from module.logger import logger

            try:
                default_value = self.model_fields[val_error_key].default
                kwargs[val_error_key] = self.model_fields[val_error_key].default
                logger.warning(f'Field {val_error_key} is out of range, using default value {default_value}')
                logger.warning(repr(exc))
                logger.warning(str(kwargs))
                super().__init__(*args, **kwargs)
            except Exception as e:
                raise


