# This Python file uses the following encoding: utf-8
# 大富翁步骤进度记录（断点续跑），参考 tasks/AbyssShadows 的 saved_params 实现
from datetime import datetime

from module.logger import logger


class RichManProgress:
    """按周记录大富翁已完成的步骤

    - 步骤执行成功后才写进 config.rich_man.saved_params.done
    - 任务中途报错退出（如游戏卡死重启）后重跑时，已完成的步骤直接跳过，从报错那一步继续
    - 跨周（ISO 周）自动清空，与大富翁每周运行一次、每周一刷新的周期一致
    """

    def init_progress(self):
        """读取本周进度，跨周则清空。幂等，可重复调用"""
        if getattr(self, '_done_steps', None) is not None:
            return
        con = self.config.rich_man.saved_params
        week = self._current_week()
        if con.save_week != week:
            if con.done:
                logger.info(f'RichMan: saved progress is of {con.save_week}, week changed, clear it')
            con.save_week = week
            con.done = ''
            self.config.save()
        self._done_steps = set(s for s in (con.done or '').split(',') if s)
        logger.info(f'RichMan done steps: {sorted(self._done_steps)}')

    def is_step_done(self, name: str) -> bool:
        self.init_progress()
        return name in self._done_steps

    def mark_step_done(self, name: str):
        self.init_progress()
        if name in self._done_steps:
            return
        self._done_steps.add(name)
        self.config.rich_man.saved_params.done = ','.join(sorted(self._done_steps))
        self.config.save()
        logger.info(f'RichMan step [{name}] done and saved')

    def run_step(self, name: str, func):
        """执行一个步骤：已完成则跳过；执行成功才记录（报错不记录，重跑从这里继续）"""
        if self.is_step_done(name):
            logger.info(f'RichMan step [{name}] is already done, skip')
            return
        func()
        self.mark_step_done(name)

    @staticmethod
    def _current_week() -> str:
        year, week, _ = datetime.now().isocalendar()
        return f'{year}-W{week:02d}'
