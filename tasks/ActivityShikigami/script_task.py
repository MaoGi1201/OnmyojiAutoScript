# This Python file uses the following encoding: utf-8
# @author AzurTian
from module.logger import logger

from tasks.ActivityShikigami.activities.direct import DirectClimbAct
from tasks.ActivityShikigami.activities.fake_god import FakeGodAct
from tasks.ActivityShikigami.activities.normal import NormalClimbAct
from tasks.ActivityShikigami.activities.rich_man import RichManAct
from tasks.base_task import BaseTask


class ScriptTask(BaseTask):

    def run(self):
        conf = self.config.model.activity_shikigami
        mode = str(getattr(conf, 'entrance_mode', 'normal') or 'normal').strip().lower()
        if mode == 'direct':
            DirectClimbAct(self.config, self.device).run()
            return
        if mode != 'normal':
            logger.warning(f'Unknown entrance mode: {mode}, fallback to normal')
        NormalClimbAct(self.config, self.device).run()


if __name__ == '__main__':
    print([1, 2, 3][2])
