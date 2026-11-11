# This Python file uses the following encoding: utf-8
# @author AzurTian
from tasks.ActivityShikigami.activities.normal import NormalClimbAct
from tasks.base_task import BaseTask


class ScriptTask(BaseTask):
    #活动爬塔入口。

    def run(self):
        # 换入口形态改 NormalClimbAct.ENTRY_GROUPS：
        #   一个类型一组 = 各类型独立入口；多个类型一组 = 共用入口靠切换按钮互切。
        # 当期：ap / pass 共用一个入口（经大地の共鳴地图页中转，靠切换按钮互换），boss 独立入口。
        NormalClimbAct(self.config, self.device).run()


if __name__ == '__main__':
    print([1, 2, 3][2])
